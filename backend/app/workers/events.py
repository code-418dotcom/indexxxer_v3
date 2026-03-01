"""
Worker-side event emission to Redis Streams.

Each indexing job has its own stream: job:{job_id}:events
Events are consumed by GET /api/v1/jobs/{id}/stream (SSE endpoint).

Usage (from any Celery task):
    from app.workers.events import emit
    emit(job_id, "file.done", file_path="foo.jpg", media_type="image")
"""

from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger(__name__)

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
