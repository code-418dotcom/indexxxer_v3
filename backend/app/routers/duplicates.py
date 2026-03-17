"""Duplicate detection API endpoints."""

import os

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_db
from app.models.gallery import Gallery
from app.models.media_item import MediaItem
from app.services.media_service import to_media_summary, WITH_TAGS_AND_PERFORMERS

router = APIRouter(prefix="/duplicates", tags=["duplicates"])


@router.post("/backfill")
async def backfill_dedup(
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger two-phase dedup for all pending media items and galleries."""
    from app.workers.tasks.phash import backfill_dedup_task

    media_pending = (await db.execute(
        select(func.count(MediaItem.id)).where(
            MediaItem.dedup_status == "pending",
            MediaItem.index_status == "indexed",
        )
    )).scalar_one()

    gallery_pending = (await db.execute(
        select(func.count(Gallery.id)).where(Gallery.dedup_status == "pending")
    )).scalar_one()

    result = backfill_dedup_task.apply_async(queue="hashing")
    return {
        "task_id": result.id,
        "status": "dispatched",
        "media_pending": media_pending,
        "gallery_pending": gallery_pending,
    }


@router.get("/stats")
async def duplicate_stats(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Return dedup statistics for media items and galleries."""
    total_items = (await db.execute(
        select(func.count(MediaItem.id))
    )).scalar_one()

    dedup_done = (await db.execute(
        select(func.count(MediaItem.id)).where(MediaItem.dedup_status == "done")
    )).scalar_one()

    dedup_pending = (await db.execute(
        select(func.count(MediaItem.id)).where(MediaItem.dedup_status == "pending")
    )).scalar_one()

    dedup_computing = (await db.execute(
        select(func.count(MediaItem.id)).where(MediaItem.dedup_status == "computing")
    )).scalar_one()

    dedup_error = (await db.execute(
        select(func.count(MediaItem.id)).where(MediaItem.dedup_status == "error")
    )).scalar_one()

    # Media duplicate stats
    dup_items = (await db.execute(
        select(func.count(MediaItem.id)).where(MediaItem.duplicate_group.isnot(None))
    )).scalar_one()

    dup_groups = (await db.execute(
        select(func.count(func.distinct(MediaItem.duplicate_group))).where(
            MediaItem.duplicate_group.isnot(None)
        )
    )).scalar_one()

    # Wasted space
    if dup_groups > 0:
        total_dup_size = (await db.execute(
            select(func.coalesce(func.sum(MediaItem.file_size), 0)).where(
                MediaItem.duplicate_group.isnot(None)
            )
        )).scalar_one()
        kept_size_subq = (
            select(
                MediaItem.duplicate_group,
                func.min(MediaItem.file_size).label("min_size"),
            )
            .where(MediaItem.duplicate_group.isnot(None))
            .group_by(MediaItem.duplicate_group)
            .subquery()
        )
        kept_size = (await db.execute(
            select(func.coalesce(func.sum(kept_size_subq.c.min_size), 0))
        )).scalar_one()
        wasted_bytes = total_dup_size - kept_size
    else:
        wasted_bytes = 0

    # Gallery duplicate stats
    gallery_total = (await db.execute(
        select(func.count(Gallery.id))
    )).scalar_one()

    gallery_dup_items = (await db.execute(
        select(func.count(Gallery.id)).where(Gallery.duplicate_group.isnot(None))
    )).scalar_one()

    gallery_dup_groups = (await db.execute(
        select(func.count(func.distinct(Gallery.duplicate_group))).where(
            Gallery.duplicate_group.isnot(None)
        )
    )).scalar_one()

    return {
        "total_items": total_items,
        "dedup_done": dedup_done,
        "dedup_pending": dedup_pending,
        "dedup_computing": dedup_computing,
        "dedup_error": dedup_error,
        "progress_pct": round(dedup_done / total_items * 100, 1) if total_items > 0 else 0,
        "duplicate_items": dup_items,
        "duplicate_groups": dup_groups,
        "wasted_bytes": wasted_bytes,
        "gallery_total": gallery_total,
        "gallery_duplicate_items": gallery_dup_items,
        "gallery_duplicate_groups": gallery_dup_groups,
    }


@router.get("")
async def list_duplicate_groups(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """List all media duplicate groups with their items."""
    group_query = (
        select(MediaItem.duplicate_group, func.count(MediaItem.id).label("count"))
        .where(MediaItem.duplicate_group.isnot(None))
        .group_by(MediaItem.duplicate_group)
        .having(func.count(MediaItem.id) > 1)
        .order_by(func.count(MediaItem.id).desc())
    )
    groups = (await db.execute(group_query)).all()

    result = []
    for group_id, count in groups:
        items_query = (
            select(MediaItem)
            .options(*WITH_TAGS_AND_PERFORMERS)
            .where(MediaItem.duplicate_group == group_id)
            .order_by(MediaItem.file_size.desc().nulls_last())
        )
        items = (await db.execute(items_query)).scalars().all()
        group_size = sum(i.file_size or 0 for i in items)
        result.append({
            "group_id": group_id,
            "count": count,
            "total_size": group_size,
            "items": [to_media_summary(i) for i in items],
        })

    return {"groups": result, "total_groups": len(result)}


@router.get("/galleries")
async def list_gallery_duplicate_groups(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """List all gallery duplicate groups."""
    group_query = (
        select(Gallery.duplicate_group, func.count(Gallery.id).label("count"))
        .where(Gallery.duplicate_group.isnot(None))
        .group_by(Gallery.duplicate_group)
        .having(func.count(Gallery.id) > 1)
        .order_by(func.count(Gallery.id).desc())
    )
    groups = (await db.execute(group_query)).all()

    result = []
    for group_id, count in groups:
        galleries = (await db.execute(
            select(Gallery)
            .where(Gallery.duplicate_group == group_id)
            .order_by(Gallery.file_size.desc().nulls_last())
        )).scalars().all()
        total_size = sum(g.file_size or 0 for g in galleries)
        result.append({
            "group_id": group_id,
            "count": count,
            "total_size": total_size,
            "galleries": [
                {
                    "id": g.id,
                    "filename": g.filename,
                    "file_path": g.file_path,
                    "image_count": g.image_count,
                    "file_size": g.file_size,
                    "cover_url": f"/api/v1/galleries/{g.id}/cover" if g.cover_path else None,
                }
                for g in galleries
            ],
        })

    return {"groups": result, "total_groups": len(result)}


@router.delete("/{group_id}/keep/{item_id}")
async def resolve_duplicates(
    group_id: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Keep one item from a duplicate group, clear duplicate_group from all."""
    items_query = select(MediaItem).where(MediaItem.duplicate_group == group_id)
    items = (await db.execute(items_query)).scalars().all()

    for item in items:
        item.duplicate_group = None

    await db.flush()
    return {"resolved": len(items), "kept": item_id}


@router.delete("/{group_id}/keep/{item_id}/destroy")
async def destroy_duplicates(
    group_id: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Keep one item, DELETE the other files from disk and remove their DB records."""
    items_query = select(MediaItem).where(MediaItem.duplicate_group == group_id)
    items = (await db.execute(items_query)).scalars().all()

    deleted_files = 0
    deleted_bytes = 0
    errors = []

    for item in items:
        if item.id == item_id:
            item.duplicate_group = None
            continue

        try:
            if item.file_path and os.path.exists(item.file_path):
                file_size = os.path.getsize(item.file_path)
                os.remove(item.file_path)
                deleted_files += 1
                deleted_bytes += file_size
            if item.thumbnail_path and os.path.exists(item.thumbnail_path):
                os.remove(item.thumbnail_path)
        except OSError as e:
            errors.append(f"{item.filename}: {e}")

        await db.delete(item)

    await db.flush()
    return {
        "kept": item_id,
        "deleted_files": deleted_files,
        "deleted_bytes": deleted_bytes,
        "errors": errors,
    }


@router.delete("/galleries/{group_id}/keep/{gallery_id}")
async def resolve_gallery_duplicates(
    group_id: str,
    gallery_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Keep one gallery from a duplicate group, clear duplicate_group from all."""
    galleries = (await db.execute(
        select(Gallery).where(Gallery.duplicate_group == group_id)
    )).scalars().all()

    for g in galleries:
        g.duplicate_group = None

    await db.flush()
    return {"resolved": len(galleries), "kept": gallery_id}
