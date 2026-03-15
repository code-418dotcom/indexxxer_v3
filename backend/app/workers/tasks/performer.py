"""
Celery tasks for performer scraping and matching.

Tasks:
  scrape_performer_task       — scrape bio + image from freeones.com
  scrape_all_performers_task  — scrape all performers with progress events
  match_performer_task        — match one performer against all media
  match_all_performers_task   — match all performers against all media
  match_media_performers_task — match a single media item against all performers (auto, post-scan)
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from app.models.performer import Performer
from app.services.performer_scraper import (
    map_scraped_to_fields,
    save_performer_image,
    scrape_performer_by_name,
    scrape_performer_by_url,
)
from app.services.storage_service import get_performer_image_path
from app.workers.celery_app import celery_app
from app.workers.db import task_session

log = structlog.get_logger(__name__)


# ── Progress event helpers ───────────────────────────────────────────────────

_redis_client = None


def _redis():
    global _redis_client
    if _redis_client is None:
        import redis
        from app.config import settings
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def _emit_scrape_event(task_id: str, **data) -> None:
    """Write a progress event to the scrape-all Redis stream."""
    try:
        r = _redis()
        key = f"scrape-all:{task_id}"
        payload = json.dumps({"task_id": task_id, **data})
        r.xadd(key, {"data": payload}, maxlen=5000, approximate=True)
        r.expire(key, 86_400)
    except Exception:
        log.warning("scrape_event.emit_failed", exc_info=True)


@celery_app.task(
    bind=True,
    queue="indexing",
    max_retries=2,
    default_retry_delay=30,
    name="app.workers.tasks.performer.scrape_performer_task",
)
def scrape_performer_task(self, performer_id: str) -> dict:
    """Scrape a performer's bio and image from freeones.com."""
    return asyncio.run(_scrape_performer(performer_id))


async def _scrape_performer(performer_id: str) -> dict:
    async with task_session() as session:
        performer = await session.get(Performer, performer_id)
        if not performer:
            return {"error": "performer not found"}

        # Scrape from freeones
        if performer.freeones_url:
            scraped = await scrape_performer_by_url(performer.freeones_url)
        else:
            scraped = await scrape_performer_by_name(performer.name)

        if not scraped:
            log.warning("scrape_performer.no_results", performer=performer.name)
            return {"error": "scrape returned no results"}

        # Map scraped fields to model
        fields = map_scraped_to_fields(scraped)
        for field_name, value in fields.items():
            if value:  # Only update non-empty fields
                setattr(performer, field_name, value)

        # Update freeones URL if we found a bio_url
        if scraped.bio_url and not performer.freeones_url:
            performer.freeones_url = scraped.bio_url.replace("/bio", "")

        performer.scraped_at = datetime.now(timezone.utc)

        # Save profile image (pre-downloaded in-browser during scrape)
        if scraped.image_bytes or scraped.image_url:
            dest = get_performer_image_path(performer.id)
            if await save_performer_image(scraped, dest):
                performer.profile_image_path = str(dest)

        await session.flush()

    log.info(
        "scrape_performer.done",
        performer_id=performer_id,
        fields=len(fields),
        has_image=bool(scraped.image_url),
    )
    return {
        "performer_id": performer_id,
        "fields_updated": len(fields),
        "has_image": bool(scraped.image_url),
    }


@celery_app.task(
    bind=True,
    queue="indexing",
    name="app.workers.tasks.performer.scrape_all_performers_task",
)
def scrape_all_performers_task(self, task_id: str) -> dict:
    """Scrape all performers sequentially, emitting progress events."""
    return asyncio.run(_scrape_all_performers(task_id))


async def _scrape_all_performers(task_id: str) -> dict:
    async with task_session() as session:
        performers = (
            await session.execute(select(Performer).order_by(Performer.name))
        ).scalars().all()

    total = len(performers)
    _emit_scrape_event(
        task_id,
        type="scrape_all.start",
        total=total,
    )

    succeeded = 0
    failed = 0
    skipped = 0

    for i, performer in enumerate(performers):
        _emit_scrape_event(
            task_id,
            type="scrape_all.progress",
            current=i + 1,
            total=total,
            performer_id=performer.id,
            performer_name=performer.name,
            status="scraping",
        )

        try:
            result = await _scrape_performer(performer.id)
            if result.get("error"):
                _emit_scrape_event(
                    task_id,
                    type="scrape_all.item",
                    current=i + 1,
                    total=total,
                    performer_id=performer.id,
                    performer_name=performer.name,
                    status="failed",
                    error=result["error"],
                )
                failed += 1
            else:
                _emit_scrape_event(
                    task_id,
                    type="scrape_all.item",
                    current=i + 1,
                    total=total,
                    performer_id=performer.id,
                    performer_name=performer.name,
                    status="done",
                    fields_updated=result.get("fields_updated", 0),
                    has_image=result.get("has_image", False),
                )
                succeeded += 1
        except Exception as exc:
            _emit_scrape_event(
                task_id,
                type="scrape_all.item",
                current=i + 1,
                total=total,
                performer_id=performer.id,
                performer_name=performer.name,
                status="error",
                error=str(exc),
            )
            failed += 1
            log.error(
                "scrape_all.item_error",
                performer=performer.name,
                error=str(exc),
                exc_info=True,
            )

    _emit_scrape_event(
        task_id,
        type="scrape_all.complete",
        total=total,
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
    )

    return {
        "total": total,
        "succeeded": succeeded,
        "failed": failed,
    }


@celery_app.task(
    queue="indexing",
    name="app.workers.tasks.performer.match_performer_task",
)
def match_performer_task(performer_id: str) -> dict:
    """Match one performer against all media items."""
    return asyncio.run(_match_performer(performer_id))


async def _match_performer(performer_id: str) -> dict:
    from app.services import performer_service

    async with task_session() as session:
        performer = await session.get(Performer, performer_id)
        if not performer:
            return {"error": "performer not found"}

        new_links = await performer_service.match_performer_to_media(
            session, performer
        )

    return {"performer_id": performer_id, "new_links": new_links}


@celery_app.task(
    queue="indexing",
    name="app.workers.tasks.performer.match_all_performers_task",
)
def match_all_performers_task() -> dict:
    """Match all performers against all media items."""
    return asyncio.run(_match_all())


async def _match_all() -> dict:
    from app.services import performer_service

    async with task_session() as session:
        results = await performer_service.match_all_performers(session)

    return {"matched": results, "total_performers": len(results)}


@celery_app.task(
    queue="indexing",
    name="app.workers.tasks.performer.match_media_performers_task",
)
def match_media_performers_task(
    media_id: str, filename: str, file_path: str
) -> dict:
    """
    Match a single newly-scanned media item against all known performers.
    Called automatically from the scan pipeline.
    """
    return asyncio.run(_match_media(media_id, filename, file_path))


async def _match_media(media_id: str, filename: str, file_path: str) -> dict:
    from app.services import performer_service

    async with task_session() as session:
        matched = await performer_service.match_media_item_to_performers(
            session, media_id, filename, file_path
        )

    return {"media_id": media_id, "performers_matched": matched}
