"""
Filesystem watcher — triggers incremental indexing when files change.

Architecture:
  - Started as a background thread when the Celery worker boots
    (via worker_ready signal).
  - Uses watchdog PollingObserver by default (PollingObserver works on
    Windows NTFS mounts exposed to WSL2, where inotify is unavailable).
  - When a file event fires, dispatches process_file_task for that file.

Configuration:
  WATCHER_USE_POLLING=true   (default) — PollingObserver
  WATCHER_USE_POLLING=false  — InotifyObserver (Linux native; not WSL2)
  WATCHER_POLL_INTERVAL=60   — seconds between poll cycles
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import structlog
from celery.signals import worker_ready, worker_shutdown
from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

from app.config import settings
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)

# Registry so we can stop all observers on shutdown
_observers: list[Observer] = []
_observers_lock = threading.Lock()


# ── Watchdog event handler ─────────────────────────────────────────────────────

class MediaEventHandler(FileSystemEventHandler):
    """Dispatch a process_file_task for every relevant filesystem event."""

    def __init__(self, source_id: str, source_path: str) -> None:
        super().__init__()
        self.source_id = source_id
        self.source_path = source_path
        # Import here to avoid circular imports at module load time
        from app.extractors.image import IMAGE_EXTENSIONS
        from app.extractors.video import VIDEO_EXTENSIONS
        self._valid_extensions = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

    def _is_media(self, path: str) -> bool:
        return Path(path).suffix.lower() in self._valid_extensions

    def _dispatch_process(self, file_path: str) -> None:
        from app.workers.tasks.scan import process_file_task

        # We don't have a job_id for watcher-triggered tasks.
        # Use a sentinel "watcher" string — process_file_task handles this
        # by skipping the job counter update when job_id == "watcher".
        process_file_task.apply_async(
            kwargs={
                "source_id": self.source_id,
                "job_id": "watcher",
                "file_path": file_path,
            },
            queue="indexing",
        )
        log.info("watcher.dispatched", path=file_path)

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        if not event.is_directory and self._is_media(event.src_path):
            self._dispatch_process(event.src_path)

    def on_modified(self, event: FileModifiedEvent) -> None:  # type: ignore[override]
        if not event.is_directory and self._is_media(event.src_path):
            self._dispatch_process(event.src_path)

    def on_moved(self, event: FileMovedEvent) -> None:  # type: ignore[override]
        # File renamed/moved within the watched tree.
        # Dispatch for the new path; hash-based deduplication will reconcile.
        if not event.is_directory and self._is_media(event.dest_path):
            self._dispatch_process(event.dest_path)

    def on_deleted(self, event: FileDeletedEvent) -> None:  # type: ignore[override]
        # Mark the item as stale. Full cleanup is handled by the next scan.
        # For now, just log. TODO M4: mark index_status='deleted'.
        if not event.is_directory and self._is_media(event.src_path):
            log.info("watcher.file_deleted", path=event.src_path)


# ── Source discovery ───────────────────────────────────────────────────────────

async def _get_enabled_sources() -> list[tuple[str, str]]:
    """Return [(source_id, path)] for all enabled MediaSources."""
    from sqlalchemy import select

    from app.models.media_source import MediaSource
    from app.workers.db import task_session

    async with task_session() as session:
        result = await session.execute(
            select(MediaSource.id, MediaSource.path).where(
                MediaSource.enabled.is_(True)
            )
        )
        return [(row.id, row.path) for row in result]


# ── Observer management ────────────────────────────────────────────────────────

def start_watcher() -> None:
    """
    Query enabled sources and start a watchdog observer for each path.
    Called from the worker_ready signal — runs in the worker process.
    """
    try:
        sources = asyncio.run(_get_enabled_sources())
    except Exception as exc:
        log.error("watcher.sources_query_failed", error=str(exc))
        sources = []

    if not sources:
        log.info("watcher.no_sources")
        return

    ObserverClass = PollingObserver if settings.watcher_use_polling else Observer

    with _observers_lock:
        for source_id, path in sources:
            root = Path(path)
            if not root.exists():
                log.warning("watcher.path_missing", path=str(root))
                continue

            handler = MediaEventHandler(source_id=source_id, source_path=path)

            if settings.watcher_use_polling:
                observer = ObserverClass(timeout=settings.watcher_poll_interval)
            else:
                observer = ObserverClass()

            observer.schedule(handler, str(root), recursive=True)
            observer.start()
            _observers.append(observer)

            log.info(
                "watcher.started",
                source_id=source_id,
                path=str(root),
                mode="polling" if settings.watcher_use_polling else "inotify",
                interval=settings.watcher_poll_interval if settings.watcher_use_polling else "n/a",
            )


def stop_all_watchers() -> None:
    with _observers_lock:
        for obs in _observers:
            obs.stop()
        for obs in _observers:
            obs.join(timeout=10)
        _observers.clear()
    log.info("watcher.stopped_all")


# ── Celery lifecycle hooks ─────────────────────────────────────────────────────

@worker_ready.connect
def _on_worker_ready(**kwargs) -> None:
    # Run watcher startup in a daemon thread so it doesn't block the signal
    t = threading.Thread(target=start_watcher, daemon=True, name="watcher-init")
    t.start()


@worker_shutdown.connect
def _on_worker_shutdown(**kwargs) -> None:
    stop_all_watchers()
