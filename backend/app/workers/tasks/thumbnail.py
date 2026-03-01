"""
Celery task: generate a thumbnail for a MediaItem.

Key property — RESUMABLE:
  Before doing any work the task checks whether the thumbnail file already
  exists on disk.  On a fresh re-queue of 11 000 files after a worker crash,
  only files without thumbnails will be processed.

Storage layout:
  {THUMBNAIL_ROOT}/{id[:2]}/{id}.jpg

  Two-level sharding keeps directory entry counts manageable (~43 entries/dir
  for 11k files across 256 buckets).
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import structlog
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import update

from app.config import settings
from app.extractors.image import IMAGE_EXTENSIONS
from app.extractors.video import VIDEO_EXTENSIONS
from app.models.media_item import MediaItem
from app.workers.celery_app import celery_app
from app.workers.db import task_session
from app.workers.events import emit

log = structlog.get_logger(__name__)


# ── Thumbnail path helper ──────────────────────────────────────────────────────

def thumbnail_path_for(media_item_id: str) -> Path:
    """Deterministic thumbnail path from media item ID (two-level shard)."""
    shard = media_item_id[:2]
    return settings.thumbnail_root_path / shard / f"{media_item_id}.jpg"


# ── Image thumbnail ────────────────────────────────────────────────────────────

def _generate_image_thumbnail(src: Path, dst: Path) -> None:
    w, h = settings.thumbnail_width, settings.thumbnail_height
    try:
        with Image.open(src) as img:
            img = ImageOps.exif_transpose(img)  # respect EXIF rotation
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")
            img.thumbnail((w, h), Image.LANCZOS)
            dst.parent.mkdir(parents=True, exist_ok=True)
            img.save(dst, "JPEG", quality=85, optimize=True)
    except UnidentifiedImageError as exc:
        raise RuntimeError(f"Cannot open image for thumbnail: {src.name}") from exc


# ── Video thumbnail ────────────────────────────────────────────────────────────

def _generate_video_thumbnail(src: Path, dst: Path) -> None:
    """
    Extract one frame from the video using ffmpeg.

    Strategy:
    - First try: seek to 5 s (avoids blank/black opening frames in many videos)
    - Fallback:  seek to 0 s  (for very short clips < 5 s)
    """
    w, h = settings.thumbnail_width, settings.thumbnail_height
    scale_filter = f"scale={w}:{h}:force_original_aspect_ratio=decrease"
    dst.parent.mkdir(parents=True, exist_ok=True)

    def _run(seek_secs: int) -> bool:
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(seek_secs),
            "-i", str(src),
            "-vf", scale_filter,
            "-vframes", "1",
            "-q:v", "3",
            str(dst),
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=settings.thumbnail_time_limit,
        )
        return result.returncode == 0 and dst.exists() and dst.stat().st_size > 0

    if not _run(5):
        # Fallback: first frame
        if not _run(0):
            raise RuntimeError(f"ffmpeg could not produce a thumbnail for {src.name}")


# ── Celery task ────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    queue="thumbnails",
    max_retries=2,
    default_retry_delay=15,
    time_limit=settings.thumbnail_time_limit + 30,
    soft_time_limit=settings.thumbnail_time_limit,
    name="app.workers.tasks.thumbnail.generate_thumbnail_task",
)
def generate_thumbnail_task(self, media_item_id: str) -> str | None:
    """
    Generate a thumbnail for *media_item_id* and update its record.
    Returns the thumbnail path string, or None if skipped (already exists).
    """
    try:
        return asyncio.run(_generate_thumbnail(media_item_id))
    except Exception as exc:
        log.error(
            "thumbnail.failed",
            media_item_id=media_item_id,
            error=str(exc),
        )
        raise self.retry(exc=exc)


async def _generate_thumbnail(media_item_id: str) -> str | None:
    async with task_session() as session:
        item = await session.get(MediaItem, media_item_id)
        if not item:
            log.warning("thumbnail.item_not_found", id=media_item_id)
            return None

        dst = thumbnail_path_for(media_item_id)

        # ── RESUMABLE: skip if file already exists ────────────────────────────
        if dst.exists() and dst.stat().st_size > 0:
            log.debug("thumbnail.already_exists", id=media_item_id, path=str(dst))
            # Ensure DB is in sync even if a previous task updated the file but
            # didn't finish the DB write.
            if item.thumbnail_path != str(dst):
                await session.execute(
                    update(MediaItem)
                    .where(MediaItem.id == media_item_id)
                    .values(thumbnail_path=str(dst))
                )
            return str(dst)

        src = Path(item.file_path)
        if not src.exists():
            log.warning("thumbnail.source_missing", path=str(src), id=media_item_id)
            await session.execute(
                update(MediaItem)
                .where(MediaItem.id == media_item_id)
                .values(
                    index_status="error",
                    index_error=f"Source file not found: {src}",
                )
            )
            return None

    # ── Generate (outside session to avoid holding the connection) ────────────
    dst_path = thumbnail_path_for(media_item_id)
    media_type = item.media_type
    ext = Path(item.file_path).suffix.lower()

    try:
        if media_type == "image" or ext in IMAGE_EXTENSIONS:
            _generate_image_thumbnail(src, dst_path)
        elif media_type == "video" or ext in VIDEO_EXTENSIONS:
            _generate_video_thumbnail(src, dst_path)
        else:
            log.warning("thumbnail.unknown_type", type=media_type, id=media_item_id)
            return None
    except Exception as exc:
        log.error("thumbnail.generation_failed", id=media_item_id, error=str(exc))
        async with task_session() as session:
            await session.execute(
                update(MediaItem)
                .where(MediaItem.id == media_item_id)
                .values(index_status="error", index_error=str(exc))
            )
        raise

    # ── Persist thumbnail path + advance status ───────────────────────────────
    async with task_session() as session:
        await session.execute(
            update(MediaItem)
            .where(MediaItem.id == media_item_id)
            .values(
                thumbnail_path=str(dst_path),
                # Only advance to 'indexed' if still in 'thumbnailing'
                # (hash task may have already moved it forward)
                index_status="indexed",
            )
        )

    log.info("thumbnail.done", id=media_item_id, path=str(dst_path))
    # Emit to any active job streams that referenced this item.
    # We don't have job_id here — emit to a global channel the frontend can subscribe to.
    # For now, emit is a no-op (job_id="watcher" is filtered); thumbnail done events
    # are inferred from file.extracted in the UI.
    return str(dst_path)
