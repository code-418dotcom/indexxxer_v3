"""
Celery tasks for two-phase deduplication.

Phase 1: Pre-filter by duration (±2%) + resolution for videos, resolution for images.
Phase 2: Multi-frame pHash comparison for videos, single pHash for images.

Gallery dedup: sample 4 images from the gallery, compute content_hash fingerprint.
"""

from __future__ import annotations

import asyncio
import io
import shutil
import zipfile
from pathlib import Path

import structlog
from sqlalchemy import select

from app.models.base import new_uuid
from app.models.frame_hash import MediaFrameHash
from app.models.gallery import Gallery, GalleryImage
from app.models.media_item import MediaItem
from app.services.dedup_service import (
    HAMMING_THRESHOLD,
    compare_frame_hashes,
    compute_gallery_content_hash,
    compute_phash,
    duration_range,
    extract_video_frames,
    hamming_distance,
)
from app.workers.celery_app import celery_app
from app.workers.db import task_session

log = structlog.get_logger(__name__)


# ── Media dedup task ──────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    queue="hashing",
    max_retries=2,
    default_retry_delay=20,
    name="app.workers.tasks.phash.compute_dedup_task",
)
def compute_dedup_task(self, media_item_id: str) -> dict:
    """Two-phase dedup for a single media item."""
    try:
        return asyncio.run(_dedup_media(media_item_id))
    except Exception as exc:
        log.error("dedup.failed", id=media_item_id, error=str(exc))
        asyncio.run(_set_dedup_status(media_item_id, "error"))
        raise self.retry(exc=exc)


async def _set_dedup_status(media_item_id: str, status: str) -> None:
    async with task_session() as session:
        item = await session.get(MediaItem, media_item_id)
        if item:
            item.dedup_status = status


async def _dedup_media(media_item_id: str) -> dict:
    # Load item metadata
    async with task_session() as session:
        item = await session.get(MediaItem, media_item_id)
        if not item:
            return {"status": "not_found"}
        media_type = item.media_type
        file_path = item.file_path
        duration = item.duration_seconds
        width = item.width
        height = item.height
        item.dedup_status = "computing"

    if media_type == "video" and duration and duration > 0:
        result = await _dedup_video(media_item_id, file_path, duration, width, height)
    elif media_type == "image":
        result = await _dedup_image(media_item_id, file_path, width, height)
    else:
        async with task_session() as session:
            item = await session.get(MediaItem, media_item_id)
            if item:
                item.dedup_status = "done"
        result = {"status": "skipped", "reason": f"unsupported type: {media_type}"}

    return result


async def _dedup_video(
    media_item_id: str, file_path: str, duration: float,
    width: int | None, height: int | None,
) -> dict:
    # Extract frames and compute per-frame hashes
    frames = extract_video_frames(file_path, duration)
    if not frames:
        async with task_session() as session:
            item = await session.get(MediaItem, media_item_id)
            if item:
                item.dedup_status = "error"
        return {"status": "error", "reason": "no frames extracted"}

    frame_hashes: dict[str, str] = {}
    try:
        for label, frame_path in frames:
            frame_hashes[label] = compute_phash(str(frame_path))
    except Exception as exc:
        log.error("dedup.phash_error", id=media_item_id, error=str(exc))
        return {"status": "error", "reason": str(exc)}
    finally:
        # Clean up temp frame files
        if frames:
            tmpdir = frames[0][1].parent
            shutil.rmtree(tmpdir, ignore_errors=True)

    # Persist frame hashes + set perceptual_hash to first frame's hash
    async with task_session() as session:
        item = await session.get(MediaItem, media_item_id)
        if not item:
            return {"status": "not_found"}

        # Clear old frame hashes
        old = await session.execute(
            select(MediaFrameHash).where(MediaFrameHash.media_item_id == media_item_id)
        )
        for row in old.scalars():
            await session.delete(row)

        for label, phash in frame_hashes.items():
            session.add(MediaFrameHash(
                media_item_id=media_item_id,
                frame_position=label,
                phash=phash,
            ))

        # Backward compat: store first frame hash as perceptual_hash
        first_hash = next(iter(frame_hashes.values()))
        item.perceptual_hash = first_hash

        # ── Pre-filter: find candidates with similar duration + same resolution ──
        dur_low, dur_high = duration_range(duration)
        cand_query = (
            select(MediaItem.id)
            .where(
                MediaItem.id != media_item_id,
                MediaItem.media_type == "video",
                MediaItem.duration_seconds.between(dur_low, dur_high),
                MediaItem.dedup_status == "done",
            )
        )
        if width and height:
            cand_query = cand_query.where(
                MediaItem.width == width,
                MediaItem.height == height,
            )
        candidate_ids = list((await session.execute(cand_query)).scalars())

    # ── Phase 2: compare frame hashes ────────────────────────────────────────
    duplicate_of = None
    for cand_id in candidate_ids:
        async with task_session() as session:
            result = await session.execute(
                select(MediaFrameHash.frame_position, MediaFrameHash.phash)
                .where(MediaFrameHash.media_item_id == cand_id)
            )
            cand_hashes = {row.frame_position: row.phash for row in result}

        if not cand_hashes:
            continue

        is_dup, match_count = compare_frame_hashes(frame_hashes, cand_hashes)
        if is_dup:
            duplicate_of = cand_id
            log.info(
                "dedup.video_match",
                media_id=media_item_id,
                duplicate_of=cand_id,
                frame_matches=match_count,
            )
            break

    # ── Assign duplicate group ───────────────────────────────────────────────
    async with task_session() as session:
        item = await session.get(MediaItem, media_item_id)
        if not item:
            return {"status": "not_found"}

        if duplicate_of:
            cand = await session.get(MediaItem, duplicate_of)
            group_id = (cand.duplicate_group if cand and cand.duplicate_group else None) or new_uuid()
            item.duplicate_group = group_id
            if cand and not cand.duplicate_group:
                cand.duplicate_group = group_id

        item.dedup_status = "done"

    return {
        "status": "done",
        "type": "video",
        "frames_hashed": len(frame_hashes),
        "duplicate_of": duplicate_of,
    }


async def _dedup_image(
    media_item_id: str, file_path: str,
    width: int | None, height: int | None,
) -> dict:
    # Compute pHash on the original file
    if not Path(file_path).exists():
        async with task_session() as session:
            item = await session.get(MediaItem, media_item_id)
            if item:
                item.dedup_status = "error"
        return {"status": "error", "reason": "file not found"}

    try:
        phash = compute_phash(file_path)
    except Exception as exc:
        log.error("dedup.image_phash_error", id=media_item_id, error=str(exc))
        async with task_session() as session:
            item = await session.get(MediaItem, media_item_id)
            if item:
                item.dedup_status = "error"
        return {"status": "error", "reason": str(exc)}

    async with task_session() as session:
        item = await session.get(MediaItem, media_item_id)
        if not item:
            return {"status": "not_found"}

        item.perceptual_hash = phash

        # Pre-filter: same resolution
        cand_query = (
            select(MediaItem.id, MediaItem.perceptual_hash, MediaItem.duplicate_group)
            .where(
                MediaItem.id != media_item_id,
                MediaItem.media_type == "image",
                MediaItem.perceptual_hash.isnot(None),
                MediaItem.dedup_status == "done",
            )
        )
        if width and height:
            cand_query = cand_query.where(
                MediaItem.width == width,
                MediaItem.height == height,
            )
        candidates = (await session.execute(cand_query)).all()

        # Find best match
        best_match = None
        for cand_id, cand_hash, cand_group in candidates:
            dist = hamming_distance(phash, cand_hash)
            if dist <= HAMMING_THRESHOLD:
                best_match = (cand_id, cand_group, dist)
                log.info(
                    "dedup.image_match",
                    media_id=media_item_id,
                    duplicate_of=cand_id,
                    distance=dist,
                )
                break

        if best_match:
            cand_id, cand_group, _ = best_match
            group_id = cand_group or new_uuid()
            item.duplicate_group = group_id
            if not cand_group:
                cand = await session.get(MediaItem, cand_id)
                if cand:
                    cand.duplicate_group = group_id

        item.dedup_status = "done"

    return {
        "status": "done",
        "type": "image",
        "duplicate_of": best_match[0] if best_match else None,
    }


# ── Gallery dedup task ────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    queue="hashing",
    max_retries=2,
    default_retry_delay=30,
    name="app.workers.tasks.phash.compute_gallery_dedup_task",
)
def compute_gallery_dedup_task(self, gallery_id: str) -> dict:
    try:
        return asyncio.run(_dedup_gallery(gallery_id))
    except Exception as exc:
        log.error("dedup.gallery_failed", id=gallery_id, error=str(exc))
        raise self.retry(exc=exc)


def _sample_indices(total: int, n: int = 4) -> list[int]:
    """Pick n evenly spaced indices from [0, total), including first."""
    if total <= n:
        return list(range(total))
    step = total / n
    return [int(i * step) for i in range(n)]


async def _dedup_gallery(gallery_id: str) -> dict:
    async with task_session() as session:
        gallery = await session.get(Gallery, gallery_id)
        if not gallery:
            return {"status": "not_found"}

        gallery.dedup_status = "computing"
        await session.flush()

        file_path = gallery.file_path
        image_count = gallery.image_count

        # Load all gallery images ordered
        imgs_result = await session.execute(
            select(GalleryImage)
            .where(GalleryImage.gallery_id == gallery_id)
            .order_by(GalleryImage.index_order)
        )
        all_images = list(imgs_result.scalars())

    if not all_images:
        async with task_session() as session:
            g = await session.get(Gallery, gallery_id)
            if g:
                g.dedup_status = "done"
        return {"status": "done", "reason": "no images"}

    # Sample 4 images to hash
    sample_idxs = _sample_indices(len(all_images))
    sampled = [(all_images[i].id, all_images[i].filename) for i in sample_idxs]

    # Compute pHashes on sampled images
    phashes: dict[str, str] = {}  # image_id -> phash
    is_zip = Path(file_path).suffix.lower() == ".zip" and Path(file_path).is_file()

    try:
        if is_zip:
            with zipfile.ZipFile(file_path, "r") as zf:
                for img_id, img_name in sampled:
                    try:
                        with zf.open(img_name) as f:
                            from PIL import Image
                            img = Image.open(io.BytesIO(f.read()))
                            import imagehash
                            h = imagehash.phash(img)
                            phashes[img_id] = str(h)
                    except Exception as exc:
                        log.debug("dedup.gallery_image_error", name=img_name, error=str(exc))
        else:
            # Folder gallery — filenames are absolute paths
            for img_id, img_name in sampled:
                try:
                    h = compute_phash(img_name)
                    phashes[img_id] = h
                except Exception as exc:
                    log.debug("dedup.gallery_image_error", name=img_name, error=str(exc))
    except Exception as exc:
        log.error("dedup.gallery_hash_error", id=gallery_id, error=str(exc))
        async with task_session() as session:
            g = await session.get(Gallery, gallery_id)
            if g:
                g.dedup_status = "error"
        return {"status": "error", "reason": str(exc)}

    if not phashes:
        async with task_session() as session:
            g = await session.get(Gallery, gallery_id)
            if g:
                g.dedup_status = "done"
        return {"status": "done", "reason": "no hashes computed"}

    content_hash = compute_gallery_content_hash(list(phashes.values()))

    # Persist hashes
    async with task_session() as session:
        gallery = await session.get(Gallery, gallery_id)
        if not gallery:
            return {"status": "not_found"}

        gallery.content_hash = content_hash

        # Update phash on sampled GalleryImage rows
        for img_id, h in phashes.items():
            gi = await session.get(GalleryImage, img_id)
            if gi:
                gi.phash = h

        # ── Find candidate galleries: same image_count ──────────────────────
        cand_result = await session.execute(
            select(Gallery.id, Gallery.content_hash, Gallery.duplicate_group)
            .where(
                Gallery.id != gallery_id,
                Gallery.image_count == image_count,
                Gallery.dedup_status == "done",
                Gallery.content_hash.isnot(None),
            )
        )
        candidates = cand_result.all()

        duplicate_of = None
        for cand_id, cand_content_hash, cand_group in candidates:
            # Exact content hash match → immediate duplicate
            if cand_content_hash == content_hash:
                duplicate_of = (cand_id, cand_group)
                log.info("dedup.gallery_exact_match", gallery_id=gallery_id, duplicate_of=cand_id)
                break

            # Fuzzy: compare sampled image hashes
            cand_imgs = await session.execute(
                select(GalleryImage.phash)
                .where(
                    GalleryImage.gallery_id == cand_id,
                    GalleryImage.phash.isnot(None),
                )
                .order_by(GalleryImage.index_order)
            )
            cand_phashes = [r.phash for r in cand_imgs]
            our_phashes = list(phashes.values())

            if len(cand_phashes) >= 3 and len(our_phashes) >= 3:
                matches = 0
                for i, h1 in enumerate(our_phashes):
                    if i < len(cand_phashes) and hamming_distance(h1, cand_phashes[i]) <= 10:
                        matches += 1
                if matches >= 3:
                    duplicate_of = (cand_id, cand_group)
                    log.info(
                        "dedup.gallery_fuzzy_match",
                        gallery_id=gallery_id,
                        duplicate_of=cand_id,
                        image_matches=matches,
                    )
                    break

        if duplicate_of:
            cand_id, cand_group = duplicate_of
            group_id = cand_group or new_uuid()
            gallery.duplicate_group = group_id
            if not cand_group:
                cand_gallery = await session.get(Gallery, cand_id)
                if cand_gallery:
                    cand_gallery.duplicate_group = group_id

        gallery.dedup_status = "done"

    return {
        "status": "done",
        "type": "gallery",
        "images_hashed": len(phashes),
        "duplicate_of": duplicate_of[0] if duplicate_of else None,
    }


# ── Backfill task ─────────────────────────────────────────────────────────────

@celery_app.task(
    queue="hashing",
    name="app.workers.tasks.phash.backfill_dedup_task",
)
def backfill_dedup_task() -> dict:
    """Dispatch dedup tasks for all pending media items and galleries."""
    return asyncio.run(_backfill_dedup())


async def _backfill_dedup() -> dict:
    async with task_session() as session:
        # Media items pending dedup
        media_result = await session.execute(
            select(MediaItem.id).where(
                MediaItem.dedup_status == "pending",
                MediaItem.index_status == "indexed",
            )
        )
        media_ids = [r[0] for r in media_result.all()]

        # Galleries pending dedup
        gallery_result = await session.execute(
            select(Gallery.id).where(Gallery.dedup_status == "pending")
        )
        gallery_ids = [r[0] for r in gallery_result.all()]

    for mid in media_ids:
        compute_dedup_task.apply_async(
            kwargs={"media_item_id": mid},
            queue="hashing",
        )

    for gid in gallery_ids:
        compute_gallery_dedup_task.apply_async(
            kwargs={"gallery_id": gid},
            queue="hashing",
        )

    log.info("dedup.backfill_dispatched", media=len(media_ids), galleries=len(gallery_ids))
    return {"media_dispatched": len(media_ids), "galleries_dispatched": len(gallery_ids)}


# ── Legacy alias ──────────────────────────────────────────────────────────────

# Keep old task name registered so pending Celery messages don't fail
@celery_app.task(
    bind=True,
    queue="hashing",
    max_retries=2,
    default_retry_delay=20,
    name="app.workers.tasks.phash.compute_phash_task",
)
def compute_phash_task(self, media_item_id: str) -> dict:
    """Legacy alias — delegates to compute_dedup_task."""
    return compute_dedup_task(media_item_id)


@celery_app.task(
    queue="hashing",
    name="app.workers.tasks.phash.backfill_phash_task",
)
def backfill_phash_task() -> dict:
    """Legacy alias — delegates to backfill_dedup_task."""
    return backfill_dedup_task()
