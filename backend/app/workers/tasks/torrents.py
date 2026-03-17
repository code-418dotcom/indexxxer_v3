"""Celery tasks for polling Transmission and processing completed torrent downloads."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog

from app.workers.celery_app import celery_app
from app.workers.db import task_session

log = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    queue="indexing",
    name="app.workers.tasks.torrents.poll_transmission_task",
    ignore_result=True,
)
def poll_transmission_task(self) -> None:
    """Periodic: check Transmission for indexxxer-labeled torrents and process completions."""
    from app.config import settings

    if not settings.transmission_host:
        return

    try:
        asyncio.run(_poll_transmission())
    except Exception:
        log.exception("torrents.poll_failed")


async def _poll_transmission() -> None:
    from app.services import transmission_service, torrent_download_service

    try:
        torrents = transmission_service.get_indexxxer_torrents()
    except Exception:
        log.warning("torrents.transmission_unreachable")
        return

    if not torrents:
        return

    async with task_session() as session:
        for torrent in torrents:
            dl = await torrent_download_service.get_by_hash(session, torrent.hashString)
            if not dl:
                continue

            # Update progress for in-flight downloads
            if torrent.progress < 100:
                dl.progress = round(torrent.progress, 1)
                if dl.status == "pending":
                    dl.status = "downloading"
                continue

            # Torrent is complete — process it
            if dl.status in ("pending", "downloading"):
                await _handle_completed(session, dl, torrent)

        await session.commit()


async def _handle_completed(session, dl, torrent) -> None:
    from app.services.torrent_download_service import move_completed_files
    from app.models.performer import Performer

    dl.status = "moving"
    dl.progress = 100.0
    await session.flush()

    # Look up performer name
    performer = await session.get(Performer, dl.performer_id) if dl.performer_id else None
    performer_name = performer.name if performer else "Unknown"

    try:
        dest_dir, moved_files = move_completed_files(
            torrent_name=torrent.name,
            download_dir=torrent.download_dir,
            performer_name=performer_name,
        )
        dl.destination_path = dest_dir
        dl.status = "completed"
        dl.completed_at = datetime.now(timezone.utc)

        # Remove torrent from Transmission (data already moved)
        from app.services import transmission_service

        try:
            transmission_service.remove_torrent(torrent.hashString, delete_data=True)
        except Exception:
            log.warning("torrents.remove_failed", hash=torrent.hashString)

        # Trigger indexing of moved files
        await _dispatch_scan(session, moved_files)

        log.info(
            "torrents.completed",
            title=dl.title,
            dest=dest_dir,
            files=len(moved_files),
        )

    except Exception as e:
        dl.status = "error"
        dl.status_error = str(e)
        log.error("torrents.move_failed", title=dl.title, error=str(e))


async def _dispatch_scan(session, file_paths: list[str]) -> None:
    """Dispatch process_file_task for each moved file to index them."""
    from app.workers.tasks.scan import process_file_task
    from sqlalchemy import select
    from app.models.media_source import MediaSource

    if not file_paths:
        return

    # Find a source that covers these files
    result = await session.execute(
        select(MediaSource).where(MediaSource.enabled.is_(True))
    )
    sources = result.scalars().all()
    source_id = None
    for src in sources:
        if file_paths[0].startswith(src.path):
            source_id = src.id
            break

    if not source_id:
        log.warning("torrents.no_source_for_scan", path=file_paths[0])
        return

    for fp in file_paths:
        process_file_task.apply_async(
            kwargs={
                "source_id": source_id,
                "job_id": "torrent",  # sentinel like "watcher"
                "file_path": fp,
            },
            queue="indexing",
        )
