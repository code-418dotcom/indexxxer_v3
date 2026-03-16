"""Duplicate detection API endpoints."""

import os

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_db
from app.models.media_item import MediaItem
from app.services.media_service import to_media_summary, WITH_TAGS_AND_FACES

router = APIRouter(prefix="/duplicates", tags=["duplicates"])


@router.post("/backfill")
async def backfill_phash(
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger pHash computation for all indexed items that don't have one yet."""
    from app.workers.tasks.phash import backfill_phash_task

    # Return count of items that will be processed
    pending = (await db.execute(
        select(func.count(MediaItem.id)).where(
            MediaItem.perceptual_hash.is_(None),
            MediaItem.thumbnail_path.isnot(None),
        )
    )).scalar_one()

    result = backfill_phash_task.apply_async(queue="hashing")
    return {"task_id": result.id, "status": "dispatched", "pending": pending}


@router.get("/stats")
async def duplicate_stats(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Return dedup scan statistics."""
    total_items = (await db.execute(
        select(func.count(MediaItem.id))
    )).scalar_one()

    hashed_items = (await db.execute(
        select(func.count(MediaItem.id)).where(MediaItem.perceptual_hash.isnot(None))
    )).scalar_one()

    pending_items = (await db.execute(
        select(func.count(MediaItem.id)).where(
            MediaItem.perceptual_hash.is_(None),
            MediaItem.thumbnail_path.isnot(None),
        )
    )).scalar_one()

    no_thumbnail = (await db.execute(
        select(func.count(MediaItem.id)).where(
            MediaItem.perceptual_hash.is_(None),
            MediaItem.thumbnail_path.is_(None),
        )
    )).scalar_one()

    # Duplicate stats
    dup_items = (await db.execute(
        select(func.count(MediaItem.id)).where(MediaItem.duplicate_group.isnot(None))
    )).scalar_one()

    dup_groups = (await db.execute(
        select(func.count(func.distinct(MediaItem.duplicate_group))).where(
            MediaItem.duplicate_group.isnot(None)
        )
    )).scalar_one()

    # Wasted space: sum file_size of all duplicate items except the first in each group
    # (approximate: total dup size minus one item per group)
    if dup_groups > 0:
        # Total size of all items in duplicate groups
        total_dup_size = (await db.execute(
            select(func.coalesce(func.sum(MediaItem.file_size), 0)).where(
                MediaItem.duplicate_group.isnot(None)
            )
        )).scalar_one()
        # Size of one (smallest) item per group
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

    return {
        "total_items": total_items,
        "hashed_items": hashed_items,
        "pending_items": pending_items,
        "no_thumbnail": no_thumbnail,
        "progress_pct": round(hashed_items / total_items * 100, 1) if total_items > 0 else 0,
        "duplicate_items": dup_items,
        "duplicate_groups": dup_groups,
        "wasted_bytes": wasted_bytes,
    }


@router.get("")
async def list_duplicate_groups(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """List all duplicate groups with their media items."""
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
            .options(*WITH_TAGS_AND_FACES)
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


@router.delete("/{group_id}/keep/{item_id}")
async def resolve_duplicates(
    group_id: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Keep one item from a duplicate group, remove duplicate_group from all in the group."""
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
            # This is the one to keep — just clear the group
            item.duplicate_group = None
            continue

        # Delete the file from disk
        try:
            if item.file_path and os.path.exists(item.file_path):
                file_size = os.path.getsize(item.file_path)
                os.remove(item.file_path)
                deleted_files += 1
                deleted_bytes += file_size
            # Also delete thumbnail if exists
            if item.thumbnail_path and os.path.exists(item.thumbnail_path):
                os.remove(item.thumbnail_path)
        except OSError as e:
            errors.append(f"{item.filename}: {e}")

        # Delete the DB record
        await db.delete(item)

    await db.flush()
    return {
        "kept": item_id,
        "deleted_files": deleted_files,
        "deleted_bytes": deleted_bytes,
        "errors": errors,
    }
