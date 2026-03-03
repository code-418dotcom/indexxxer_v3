"""
Celery task: compute a partial SHA-256 fingerprint for a MediaItem.

WHY PARTIAL?
  Full SHA-256 of a 50 GB video would take 10–15 minutes. For a ~3 TB library
  this is impractical. Instead we hash the first 1 MB of the file plus its
  size, which is unique in practice for media files (headers differ between
  all files of any significance) and runs in < 10 ms regardless of file size.

DEDUPLICATION:
  After writing file_hash, we check if another MediaItem already carries the
  same hash with a different primary key.  If so, the current item is a
  renamed/moved copy of the existing one.  We transfer its tags and path to
  the canonical record and delete the duplicate.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import structlog
from sqlalchemy import select

from app.models.media_item import MediaItem
from app.models.tag import MediaTag
from app.workers.celery_app import celery_app
from app.workers.db import task_session

log = structlog.get_logger(__name__)

_HASH_CHUNK = 1 * 1024 * 1024  # 1 MB


# ── Hashing helper ─────────────────────────────────────────────────────────────

def partial_sha256(path: Path, chunk_bytes: int = _HASH_CHUNK) -> str:
    """
    SHA-256 of first *chunk_bytes* bytes of *path* + its total size.

    The size suffix ensures two truncated files with the same first chunk
    produce different fingerprints.
    """
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        data = fh.read(chunk_bytes)
    h.update(data)
    total_size = path.stat().st_size
    h.update(total_size.to_bytes(8, "little"))
    return h.hexdigest()


# ── Celery task ────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    queue="hashing",
    max_retries=2,
    default_retry_delay=20,
    name="app.workers.tasks.hashing.compute_hash_task",
)
def compute_hash_task(self, media_item_id: str) -> str | None:
    """
    Compute partial SHA-256 for *media_item_id* and handle deduplication.
    Returns the hash string, or None if the item was not found.
    """
    try:
        return asyncio.run(_compute_hash(media_item_id))
    except Exception as exc:
        log.error("hash.failed", id=media_item_id, error=str(exc))
        raise self.retry(exc=exc)


async def _compute_hash(media_item_id: str) -> str | None:
    async with task_session() as session:
        item = await session.get(MediaItem, media_item_id)
        if not item:
            log.warning("hash.item_not_found", id=media_item_id)
            return None

        src = Path(item.file_path)
        if not src.exists():
            log.warning("hash.source_missing", path=str(src))
            return None

    # Compute outside session (I/O — don't hold DB connection)
    try:
        digest = partial_sha256(src)
    except OSError as exc:
        log.error("hash.io_error", path=str(src), error=str(exc))
        return None

    # Check for an existing MediaItem with the same hash (rename/move detection)
    async with task_session() as session:
        result = await session.execute(
            select(MediaItem).where(
                MediaItem.file_hash == digest,
                MediaItem.id != media_item_id,
            )
        )
        canonical = result.scalar_one_or_none()

        if canonical is not None:
            # ── Deduplication: current item is a duplicate of canonical ───────
            log.info(
                "hash.duplicate_detected",
                new_id=media_item_id,
                canonical_id=canonical.id,
                old_path=canonical.file_path,
                new_path=item.file_path,
            )
            # Re-load current item (separate session above may be stale)
            dup = await session.get(MediaItem, media_item_id)
            if dup:
                # Transfer any manual tags from dup to canonical
                dup_tags = await session.execute(
                    select(MediaTag).where(
                        MediaTag.media_id == media_item_id,
                        MediaTag.source == "manual",
                    )
                )
                for mt in dup_tags.scalars():
                    existing_tag = await session.execute(
                        select(MediaTag).where(
                            MediaTag.media_id == canonical.id,
                            MediaTag.tag_id == mt.tag_id,
                        )
                    )
                    if not existing_tag.scalar_one_or_none():
                        session.add(
                            MediaTag(
                                media_id=canonical.id,
                                tag_id=mt.tag_id,
                                source="manual",
                                confidence=1.0,
                            )
                        )
                # Delete dup FIRST so it releases the (source_id, file_path)
                # unique constraint slot before we update canonical's path.
                await session.delete(dup)
                await session.flush()

            # Update canonical's path if the new location is different.
            # Safe to do now that dup has been flushed/deleted.
            if canonical.file_path != item.file_path:
                canonical.file_path = item.file_path
                canonical.filename = src.name

        else:
            # ── No duplicate: just write the hash ─────────────────────────────
            fresh = await session.get(MediaItem, media_item_id)
            if fresh:
                fresh.file_hash = digest

    log.debug("hash.done", id=media_item_id, digest=digest[:12] + "...")
    return digest
