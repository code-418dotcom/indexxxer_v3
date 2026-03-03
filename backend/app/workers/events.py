"""
Worker-side event emission to Redis Streams.

Each indexing job has its own stream: job:{job_id}:events
Events are consumed by GET /api/v1/jobs/{id}/stream (SSE endpoint).

Usage (from any Celery task):
    from app.workers.events import emit
    emit(job_id, "file.done", file_path="foo.jpg", media_type="image")

For async contexts (inside async task helpers), use await emit_webhook_event(...)
"""

from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger(__name__)

# Webhook event type constants
EVENTS = {
    "scan.started",
    "scan.completed",
    "scan.failed",
    "media.indexed",
    "media.deleted",
    "tag.created",
    "ping",
}

# Lazily initialised sync redis client (one per worker process)
_redis_client = None


def _client():
    global _redis_client
    if _redis_client is None:
        import redis

        from app.config import settings

        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def emit(job_id: str, event_type: str, **data: Any) -> None:
    """
    Append a structured event to the Redis Stream for *job_id*.

    The stream is capped at 1 000 entries (MAXLEN ~) and expires after 24 h.
    Failures are swallowed so a Redis hiccup never breaks the indexing pipeline.
    """
    if job_id == "watcher":
        # Ad-hoc watcher events are not associated with a named job — skip.
        return
    try:
        payload = json.dumps({"type": event_type, "job_id": job_id, **data})
        r = _client()
        key = f"job:{job_id}:events"
        r.xadd(key, {"data": payload}, maxlen=1000, approximate=True)
        r.expire(key, 86_400)  # 24 h TTL
    except Exception:
        log.warning("events.emit_failed", exc_info=True)


async def emit_webhook_event(event_type: str, payload: dict) -> None:
    """
    Dispatch webhook delivery tasks for all enabled webhooks subscribed to event_type.
    Async — must be awaited from async code.

    Webhook flood prevention: media.indexed should only be emitted for watcher
    (incremental) events, not during bulk scans.
    """
    try:
        await _emit_webhook_event_async(event_type, payload)
    except Exception:
        log.warning("webhook_event.emit_failed", event_type=event_type, exc_info=True)


async def _emit_webhook_event_async(event_type: str, payload: dict) -> None:
    from sqlalchemy import select

    from app.models.webhook import Webhook
    from app.services import webhook_service
    from app.workers.db import task_session
    from app.workers.tasks.webhook import deliver_webhook_task

    async with task_session() as session:
        result = await session.execute(
            select(Webhook).where(Webhook.enabled.is_(True))
        )
        webhooks = result.scalars().all()

        for wh in webhooks:
            events_list = wh.events or []
            if event_type not in events_list:
                continue
            delivery = await webhook_service.record_delivery(
                session, wh.id, event_type, payload
            )
            deliver_webhook_task.apply_async(
                kwargs={
                    "delivery_id": delivery.id,
                    "webhook_id": wh.id,
                    "event_type": event_type,
                    "payload": payload,
                },
                queue="webhooks",
                countdown=0,
            )
