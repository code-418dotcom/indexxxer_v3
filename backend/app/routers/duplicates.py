"""Duplicate detection API endpoints."""

from fastapi import APIRouter, Depends
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
):
    """Trigger pHash computation for all indexed items that don't have one yet."""
    from app.workers.tasks.phash import backfill_phash_task

    result = backfill_phash_task.apply_async(queue="hashing")
    return {"task_id": result.id, "status": "dispatched"}


@router.get("")
async def list_duplicate_groups(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """List all duplicate groups with their media items."""
    # Find all groups
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
            .order_by(MediaItem.indexed_at.asc())
        )
        items = (await db.execute(items_query)).scalars().all()
        result.append({
            "group_id": group_id,
            "count": count,
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
    # Clear the group (don't delete files -- just un-flag them)
    items_query = select(MediaItem).where(MediaItem.duplicate_group == group_id)
    items = (await db.execute(items_query)).scalars().all()

    for item in items:
        item.duplicate_group = None

    await db.flush()
    return {"resolved": len(items), "kept": item_id}
