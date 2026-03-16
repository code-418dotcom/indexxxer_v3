"""
Celery task: compute perceptual hash for a MediaItem's thumbnail.

Uses pHash (DCT-based) from imagehash library on the generated thumbnail.
After computing, checks for near-duplicates (hamming distance <= 8) and
groups them under a shared duplicate_group UUID.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import imagehash
import structlog
from PIL import Image
from sqlalchemy import select

from app.models.base import new_uuid
from app.models.media_item import MediaItem
from app.workers.celery_app import celery_app
from app.workers.db import task_session

log = structlog.get_logger(__name__)

HAMMING_THRESHOLD = 4  # max hamming distance to consider as duplicate (strict — avoids false positives from similar studio branding)


def _compute_phash(thumbnail_path: str) -> str:
    """Compute 64-bit perceptual hash and return as hex string."""
    img = Image.open(thumbnail_path)
    h = imagehash.phash(img)
    return str(h)


def _hamming_distance(h1: str, h2: str) -> int:
    """Compute hamming distance between two hex hash strings."""
    hash1 = int(h1, 16)
    hash2 = int(h2, 16)
    return bin(hash1 ^ hash2).count("1")


@celery_app.task(
    bind=True,
    queue="hashing",
    max_retries=2,
    default_retry_delay=20,
    name="app.workers.tasks.phash.compute_phash_task",
)
def compute_phash_task(self, media_item_id: str) -> str | None:
    """Compute perceptual hash and detect near-duplicates."""
    try:
        return asyncio.run(_compute_phash_and_dedup(media_item_id))
    except Exception as exc:
        log.error("phash.failed", id=media_item_id, error=str(exc))
        raise self.retry(exc=exc)


async def _compute_phash_and_dedup(media_item_id: str) -> str | None:
    async with task_session() as session:
        item = await session.get(MediaItem, media_item_id)
        if not item:
            log.warning("phash.item_not_found", id=media_item_id)
            return None

        if not item.thumbnail_path or not Path(item.thumbnail_path).exists():
            log.warning("phash.no_thumbnail", id=media_item_id)
            return None

        thumbnail_path = item.thumbnail_path

    # Compute pHash outside session
    try:
        phash = _compute_phash(thumbnail_path)
    except Exception as exc:
        log.error("phash.compute_error", id=media_item_id, error=str(exc))
        return None

    # Save hash and check for near-duplicates
    async with task_session() as session:
        item = await session.get(MediaItem, media_item_id)
        if not item:
            return None

        item.perceptual_hash = phash

        # Find existing items with a perceptual hash (potential duplicates)
        result = await session.execute(
            select(MediaItem.id, MediaItem.perceptual_hash, MediaItem.duplicate_group)
            .where(
                MediaItem.perceptual_hash.isnot(None),
                MediaItem.id != media_item_id,
            )
        )
        candidates = result.all()

        # Find near-duplicates by hamming distance
        matches = []
        for cand_id, cand_hash, cand_group in candidates:
            dist = _hamming_distance(phash, cand_hash)
            if dist <= HAMMING_THRESHOLD:
                matches.append((cand_id, cand_hash, cand_group, dist))
                log.info(
                    "phash.duplicate_found",
                    media_id=media_item_id,
                    duplicate_of=cand_id,
                    distance=dist,
                )

        if matches:
            # Use existing group if any match already has one, otherwise create new
            existing_group = next(
                (g for _, _, g, _ in matches if g is not None), None
            )
            group_id = existing_group or new_uuid()

            item.duplicate_group = group_id

            # Update any matched items that don't have a group yet
            for cand_id, _, cand_group, _ in matches:
                if cand_group is None:
                    cand = await session.get(MediaItem, cand_id)
                    if cand:
                        cand.duplicate_group = group_id

    log.debug("phash.done", id=media_item_id, phash=phash)
    return phash


@celery_app.task(
    queue="hashing",
    name="app.workers.tasks.phash.backfill_phash_task",
)
def backfill_phash_task() -> dict:
    """Dispatch compute_phash_task for all items missing a perceptual hash."""
    return asyncio.run(_backfill_phash())


async def _backfill_phash() -> dict:
    async with task_session() as session:
        result = await session.execute(
            select(MediaItem.id).where(
                MediaItem.perceptual_hash.is_(None),
                MediaItem.thumbnail_path.isnot(None),
            )
        )
        ids = [r[0] for r in result.all()]

    for mid in ids:
        compute_phash_task.apply_async(
            kwargs={"media_item_id": mid},
            queue="hashing",
        )

    log.info("phash.backfill_dispatched", count=len(ids))
    return {"dispatched": len(ids)}
