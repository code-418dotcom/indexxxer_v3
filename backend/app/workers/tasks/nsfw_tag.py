"""
Celery tasks for NSFW AI auto-tagging.

Uses the nsfw_ai_model_server to analyze media files and apply tags.
"""

from __future__ import annotations

import asyncio
import re

import structlog
from sqlalchemy import select

from app.models.media_item import MediaItem
from app.models.tag import MediaTag, Tag
from app.services.nsfw_tagger import extract_tags, is_ready, tag_images, tag_video
from app.workers.celery_app import celery_app
from app.workers.db import task_session

log = structlog.get_logger(__name__)


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


async def _get_or_create_tag(session, name: str, category: str) -> str:
    """Get existing tag by slug or create a new one. Returns tag ID."""
    slug = _slugify(name)
    result = await session.execute(
        select(Tag).where(Tag.slug == slug)
    )
    tag = result.scalar_one_or_none()
    if tag:
        return tag.id

    # Assign colors by category
    category_colors = {
        "actions": "#e53e3e",
        "bdsm": "#9b2c2c",
        "bodyparts": "#3182ce",
        "positions": "#38a169",
    }
    tag = Tag(
        name=name,
        slug=slug,
        category=category,
        color=category_colors.get(category, "#718096"),
    )
    session.add(tag)
    await session.flush()
    return tag.id


async def _apply_tags(media_id: str, tags: list[tuple[str, str, float]]) -> int:
    """Apply extracted tags to a media item. Returns count of new tags applied."""
    if not tags:
        return 0

    applied = 0
    async with task_session() as session:
        for name, category, confidence in tags:
            tag_id = await _get_or_create_tag(session, name, category)

            # Check if this tag is already linked
            existing = await session.execute(
                select(MediaTag).where(
                    MediaTag.media_id == media_id,
                    MediaTag.tag_id == tag_id,
                )
            )
            if existing.scalar_one_or_none():
                continue

            session.add(
                MediaTag(
                    media_id=media_id,
                    tag_id=tag_id,
                    confidence=confidence,
                    source="ai",
                )
            )
            applied += 1

    log.info("nsfw_tag.applied", media_id=media_id, tags_applied=applied, total_tags=len(tags))
    return applied


@celery_app.task(
    bind=True,
    queue="ai",
    max_retries=2,
    default_retry_delay=60,
    name="app.workers.tasks.nsfw_tag.nsfw_tag_task",
)
def nsfw_tag_task(self, media_item_id: str) -> dict:
    """Tag a media item using the NSFW AI model server."""
    try:
        return asyncio.run(_nsfw_tag(media_item_id))
    except Exception as exc:
        log.error("nsfw_tag.failed", id=media_item_id, error=str(exc))
        raise self.retry(exc=exc)


async def _nsfw_tag(media_item_id: str) -> dict:
    # Check if tagger is available
    if not await is_ready():
        log.warning("nsfw_tag.server_not_ready", id=media_item_id)
        return {"status": "skipped", "reason": "tagger not ready"}

    async with task_session() as session:
        item = await session.get(MediaItem, media_item_id)
        if not item:
            return {"status": "skipped", "reason": "item not found"}
        file_path = item.file_path
        media_type = item.media_type

    # Call the appropriate tagger endpoint
    if media_type == "video":
        result = await tag_video(file_path)
    elif media_type == "image":
        result = await tag_images([file_path])
    else:
        return {"status": "skipped", "reason": f"unsupported type: {media_type}"}

    if not result:
        return {"status": "error", "reason": "tagger returned no result"}

    # Extract and apply tags
    tags = extract_tags(result)
    applied = await _apply_tags(media_item_id, tags)

    return {
        "status": "done",
        "tags_found": len(tags),
        "tags_applied": applied,
    }


@celery_app.task(
    queue="ai",
    name="app.workers.tasks.nsfw_tag.backfill_nsfw_tags_task",
)
def backfill_nsfw_tags_task() -> dict:
    """Dispatch nsfw_tag_task for all media items that have no AI tags."""
    return asyncio.run(_backfill_nsfw_tags())


async def _backfill_nsfw_tags() -> dict:
    async with task_session() as session:
        # Find items with no AI-sourced tags
        items_with_ai_tags = (
            select(MediaTag.media_id)
            .where(MediaTag.source == "ai")
            .distinct()
        )
        result = await session.execute(
            select(MediaItem.id).where(
                MediaItem.id.notin_(items_with_ai_tags),
                MediaItem.index_status == "indexed",
            )
        )
        ids = [r[0] for r in result.all()]

    for mid in ids:
        nsfw_tag_task.apply_async(
            kwargs={"media_item_id": mid},
            queue="ai",
        )

    log.info("nsfw_tag.backfill_dispatched", count=len(ids))
    return {"dispatched": len(ids)}
