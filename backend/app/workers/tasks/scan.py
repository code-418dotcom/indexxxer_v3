"""
Celery tasks for filesystem scanning and per-file metadata extraction.

Pipeline:
  scan_source_task
      └─ process_file_task  (one per media file)
              ├─ generate_thumbnail_task
              └─ compute_hash_task
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog
from celery import group
from sqlalchemy import select, text, update

from app.config import settings
from app.connectors.factory import get_connector
from app.extractors.base import ExtractionError
from app.workers.events import emit, emit_webhook_event
from app.extractors.image import IMAGE_EXTENSIONS, ImageExtractor
from app.extractors.video import VIDEO_EXTENSIONS, VideoExtractor
from app.models.index_job import IndexJob
from app.models.media_item import MediaItem
from app.models.media_source import MediaSource
from app.models.source_credential import SourceCredential
from app.workers.celery_app import celery_app
from app.workers.db import task_session

log = structlog.get_logger(__name__)

# All supported extensions (image + video)
_ALL_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

_image_extractor = ImageExtractor()
_video_extractor = VideoExtractor()


# ── Filesystem helpers ─────────────────────────────────────────────────────────

def _iter_media_files(root: Path, scan_config: dict | None) -> list[Path]:
    """
    Walk *root* and return a sorted list of all media file paths.

    Respects scan_config keys:
      include_extensions: list[str]  (default: all supported)
      exclude_globs:      list[str]  (patterns relative to root)
      skip_hidden:        bool       (default: True)
      max_depth:          int | None (default: None = unlimited)
    """
    cfg = scan_config or {}
    include_exts = frozenset(
        e.lower() for e in cfg.get("include_extensions", list(_ALL_EXTENSIONS))
    )
    skip_hidden: bool = cfg.get("skip_hidden", True)
    max_depth: int | None = cfg.get("max_depth")

    found: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        depth = len(current.relative_to(root).parts)

        # Prune hidden directories in-place (modifies the walk)
        if skip_hidden:
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]

        if max_depth is not None and depth > max_depth:
            dirnames.clear()
            continue

        for fname in filenames:
            if skip_hidden and fname.startswith("."):
                continue
            fpath = current / fname
            if fpath.suffix.lower() in include_exts:
                found.append(fpath)

    return sorted(found)


# ── Job counter helpers ────────────────────────────────────────────────────────

async def _increment_job_field(job_id: str, field: str) -> None:
    """
    Atomically increment a counter column on index_jobs.
    When processed + failed + skipped reaches total, marks the job completed.
    """
    async with task_session() as session:
        await session.execute(
            text(
                f"""
                UPDATE index_jobs
                SET {field} = {field} + 1,
                    status = CASE
                        WHEN processed_files + failed_files + skipped_files + 1
                             >= COALESCE(total_files, 0)
                        THEN 'completed'
                        ELSE status
                    END,
                    completed_at = CASE
                        WHEN processed_files + failed_files + skipped_files + 1
                             >= COALESCE(total_files, 0)
                        THEN NOW()
                        ELSE completed_at
                    END
                WHERE id = :job_id
                """
            ),
            {"job_id": job_id},
        )


# ── Task: full / incremental source scan ──────────────────────────────────────

@celery_app.task(
    bind=True,
    queue="indexing",
    max_retries=2,
    default_retry_delay=30,
    name="app.workers.tasks.scan.scan_source_task",
)
def scan_source_task(self, source_id: str, job_id: str) -> dict:
    """
    Walk a MediaSource's filesystem path and dispatch process_file_task
    for each file that needs indexing.

    Returns a summary dict once all tasks have been dispatched.
    """
    return asyncio.run(_scan_source(self, source_id, job_id))


async def _scan_source(task, source_id: str, job_id: str) -> dict:
    async with task_session() as session:
        source = await session.get(MediaSource, source_id)
        if not source:
            log.error("scan.source_not_found", source_id=source_id)
            return {"error": "source not found"}

        job = await session.get(IndexJob, job_id)
        if not job:
            log.error("scan.job_not_found", job_id=job_id)
            return {"error": "job not found"}

        # Mark job as running
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        await session.flush()

    # For local sources, validate the path exists before fetching connector
    if source.source_type == "local":
        root = Path(source.path)
        if not root.exists():
            async with task_session() as session:
                job = await session.get(IndexJob, job_id)
                job.status = "failed"
                job.error_message = f"Source path does not exist: {source.path}"
                job.completed_at = datetime.now(timezone.utc)
            log.error("scan.path_missing", path=str(root), source_id=source_id)
            return {"error": "path not found"}

    # Load credentials for non-local sources
    credential = None
    if source.source_type != "local":
        async with task_session() as session:
            result = await session.execute(
                select(SourceCredential).where(SourceCredential.source_id == source_id)
            )
            credential = result.scalar_one_or_none()

    connector = get_connector(source, credential)

    log.info("scan.start", source=source.name, path=str(source.path), job_id=job_id)
    emit(job_id, "scan.start", source=source.name, path=str(source.path))
    await emit_webhook_event("scan.started", {"job_id": job_id, "source_id": source_id, "source_name": source.name})

    # Collect all files via connector
    all_files = []
    async with connector:
        async for entry in connector.iter_files(source.scan_config):
            all_files.append(entry)

    total = len(all_files)
    log.info("scan.discovered", total=total, job_id=job_id)
    emit(job_id, "scan.discovered", total=total)

    # Load existing media items for this source (path → mtime) for skip detection
    async with task_session() as session:
        rows = await session.execute(
            select(MediaItem.file_path, MediaItem.file_mtime).where(
                MediaItem.source_id == source_id
            )
        )
        existing: dict[str, datetime | None] = {r.file_path: r.file_mtime for r in rows}

    # Update total_files on the job
    async with task_session() as session:
        await session.execute(
            update(IndexJob)
            .where(IndexJob.id == job_id)
            .values(total_files=total)
        )

    # Dispatch per-file tasks (or skip unchanged files)
    to_process: list[str] = []
    to_skip: int = 0

    for entry in all_files:
        fpath_str = entry.path
        mtime = entry.mtime

        known_mtime = existing.get(fpath_str)
        if known_mtime is not None:
            # Normalise to UTC for comparison
            if hasattr(known_mtime, "tzinfo") and known_mtime.tzinfo is None:
                known_mtime = known_mtime.replace(tzinfo=timezone.utc)
            if abs((mtime - known_mtime).total_seconds()) < 2:
                # mtime unchanged within 2-second tolerance → skip
                to_skip += 1
                continue

        to_process.append(fpath_str)

    # Atomically record skipped count
    if to_skip:
        async with task_session() as session:
            await session.execute(
                text(
                    "UPDATE index_jobs SET skipped_files = skipped_files + :n WHERE id = :job_id"
                ),
                {"n": to_skip, "job_id": job_id},
            )

    # If nothing needs processing, complete the job now
    if not to_process:
        async with task_session() as session:
            await session.execute(
                update(IndexJob)
                .where(IndexJob.id == job_id)
                .values(
                    status="completed",
                    completed_at=datetime.now(timezone.utc),
                )
            )
        log.info("scan.complete_no_changes", job_id=job_id, skipped=to_skip)
        emit(job_id, "scan.complete", processed=0, skipped=to_skip)
        await emit_webhook_event("scan.completed", {"job_id": job_id, "source_id": source_id, "processed": 0, "skipped": to_skip})
        return {"status": "completed", "processed": 0, "skipped": to_skip}

    # Dispatch a Celery group so tasks run in parallel
    job_group = group(
        process_file_task.s(
            source_id=source_id,
            job_id=job_id,
            file_path=fp,
        )
        for fp in to_process
    )
    job_group.apply_async()

    log.info(
        "scan.dispatched",
        job_id=job_id,
        to_process=len(to_process),
        skipped=to_skip,
    )
    emit(job_id, "scan.dispatched", dispatched=len(to_process), skipped=to_skip)
    return {"status": "running", "dispatched": len(to_process), "skipped": to_skip}


# ── Task: process a single file ────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    queue="indexing",
    max_retries=3,
    default_retry_delay=10,
    name="app.workers.tasks.scan.process_file_task",
)
def process_file_task(self, source_id: str, job_id: str, file_path: str) -> str:
    """
    Extract metadata for one file and persist a MediaItem row.
    Dispatches thumbnail and hash tasks on completion.
    Returns the media_item_id.
    """
    try:
        return asyncio.run(_process_file(source_id, job_id, file_path))
    except Exception as exc:
        log.error(
            "process_file.failed",
            path=file_path,
            error=str(exc),
            exc_info=True,
        )
        asyncio.run(_increment_job_field(job_id, "failed_files"))
        emit(job_id, "file.error", file_path=file_path, error=str(exc))
        raise self.retry(exc=exc)


async def _process_file(source_id: str, job_id: str, file_path: str) -> str:
    fpath = Path(file_path)
    log.debug("process_file.start", path=file_path)

    # ── Stat the file ────────────────────────────────────────────────────────
    try:
        stat = fpath.stat()
    except OSError as exc:
        raise ExtractionError(f"Cannot stat {file_path}: {exc}") from exc

    file_size = stat.st_size
    file_mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

    # ── Select extractor ─────────────────────────────────────────────────────
    if _image_extractor.can_handle(fpath):
        extractor = _image_extractor
    elif _video_extractor.can_handle(fpath):
        extractor = _video_extractor
    else:
        raise ExtractionError(f"No extractor for extension: {fpath.suffix}")

    # ── Extract metadata ─────────────────────────────────────────────────────
    meta = extractor.extract(fpath)

    # ── Upsert MediaItem ──────────────────────────────────────────────────────
    async with task_session() as session:
        result = await session.execute(
            select(MediaItem).where(
                MediaItem.source_id == source_id,
                MediaItem.file_path == file_path,
            )
        )
        item = result.scalar_one_or_none()

        if item is None:
            item = MediaItem(
                source_id=source_id,
                file_path=file_path,
                filename=fpath.name,
            )
            session.add(item)

        item.filename = fpath.name
        item.file_size = file_size
        item.file_mtime = file_mtime
        item.media_type = meta.media_type
        item.mime_type = meta.mime_type
        item.width = meta.width
        item.height = meta.height
        item.duration_seconds = meta.duration_seconds
        item.bitrate = meta.bitrate
        item.codec = meta.codec
        item.frame_rate = meta.frame_rate
        item.index_status = "thumbnailing"
        item.index_error = None
        item.indexed_at = datetime.now(timezone.utc)

        await session.flush()
        media_item_id = item.id

    log.info(
        "process_file.extracted",
        id=media_item_id,
        type=meta.media_type,
        path=fpath.name,
    )
    emit(
        job_id,
        "file.extracted",
        media_item_id=media_item_id,
        filename=fpath.name,
        media_type=meta.media_type,
    )

    # ── Dispatch downstream tasks ─────────────────────────────────────────────
    from app.workers.tasks.hashing import compute_hash_task
    from app.workers.tasks.thumbnail import generate_thumbnail_task

    generate_thumbnail_task.apply_async(
        kwargs={"media_item_id": media_item_id},
        queue="thumbnails",
    )
    compute_hash_task.apply_async(
        kwargs={"media_item_id": media_item_id},
        queue="hashing",
    )

    # ── Deduplication (two-phase: pre-filter + multi-frame pHash) ────────────
    from app.workers.tasks.phash import compute_dedup_task
    compute_dedup_task.apply_async(
        kwargs={"media_item_id": media_item_id},
        queue="hashing",
        countdown=10,  # wait for metadata + thumbnail
    )

    # ── Performer auto-matching ──────────────────────────────────────────────
    from app.workers.tasks.performer import match_media_performers_task
    match_media_performers_task.apply_async(
        kwargs={
            "media_id": media_item_id,
            "filename": fpath.name,
            "file_path": file_path,
        },
        queue="indexing",
        countdown=2,
    )

    # ── NSFW AI auto-tagging ─────────────────────────────────────────────────
    from app.workers.tasks.nsfw_tag import nsfw_tag_task
    nsfw_tag_task.apply_async(
        kwargs={"media_item_id": media_item_id},
        queue="ai",
        countdown=15,  # wait for thumbnail to be ready
    )

    # ── Update job progress ───────────────────────────────────────────────────
    # "watcher" is a sentinel used by the filesystem watcher for ad-hoc
    # single-file indexing that isn't associated with a named IndexJob.
    if job_id != "watcher":
        await _increment_job_field(job_id, "processed_files")

    return media_item_id


# ── Beat task: reap stalled jobs ──────────────────────────────────────────────

@celery_app.task(
    queue="indexing",
    name="app.workers.tasks.scan.reap_stalled_jobs_task",
)
def reap_stalled_jobs_task() -> int:
    """
    Safety net: mark running jobs as completed when their file counters add up,
    and mark jobs that have been running for > 2 hours without progress as failed.
    Returns the number of jobs updated.
    """
    return asyncio.run(_reap_stalled_jobs())


async def _reap_stalled_jobs() -> int:
    async with task_session() as session:
        # Complete jobs where all files are accounted for
        result_complete = await session.execute(
            text(
                """
                UPDATE index_jobs
                SET status = 'completed', completed_at = NOW()
                WHERE status = 'running'
                  AND total_files IS NOT NULL
                  AND processed_files + failed_files + skipped_files >= total_files
                """
            )
        )
        # Fail jobs that have been running > 2 hours (stuck)
        stale_cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
        result_fail = await session.execute(
            text(
                """
                UPDATE index_jobs
                SET status = 'failed',
                    completed_at = NOW(),
                    error_message = 'Job timed out after 2 hours without completion'
                WHERE status = 'running'
                  AND started_at < :cutoff
                """
            ),
            {"cutoff": stale_cutoff},
        )

    updated = (result_complete.rowcount or 0) + (result_fail.rowcount or 0)
    if updated:
        log.info("reap_stalled_jobs.updated", count=updated)
    return updated
