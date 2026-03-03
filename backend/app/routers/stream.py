"""
Server-Sent Events endpoint for live job log streaming.

GET /api/v1/jobs/{job_id}/stream
  - Streams events from the Redis stream job:{job_id}:events
  - Accepts token as query param (EventSource API cannot set custom headers)
  - Yields SSE-formatted text/event-stream until job completes or client disconnects

Event format (JSON in the data field):
  data: {"type": "file.extracted", "job_id": "...", "filename": "...", ...}
"""

from __future__ import annotations

import asyncio
import json

import structlog
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from app.config import settings
from app.core.security import decode_token
from jose import JWTError

log = structlog.get_logger(__name__)


def _validate_stream_token(token: str) -> bool:
    """Accept JWT access tokens or the static API token (backward compat)."""
    # Try JWT first
    try:
        payload = decode_token(token)
        return payload.get("type") == "access"
    except JWTError:
        pass
    # Fall back to static token
    return token == settings.api_token

router = APIRouter(prefix="/jobs", tags=["stream"])

# Terminal event types — stop streaming once we see one of these
_TERMINAL_EVENTS = {"scan.complete", "job.failed", "job.cancelled"}


@router.get(
    "/{job_id}/stream",
    summary="Stream live events for a job via SSE",
    response_class=StreamingResponse,
)
async def stream_job_events(
    job_id: str,
    request: Request,
    token: str = Query(description="API token (required — EventSource cannot send headers)"),
    from_id: str = Query(default="0", description="Resume from Redis stream ID (0 = start)"),
):
    """
    Stream structured log events for *job_id* as Server-Sent Events.

    Connect with:
        const es = new EventSource(`/api/v1/jobs/${id}/stream?token=xxx`)
        es.onmessage = (e) => console.log(JSON.parse(e.data))
    """
    if not _validate_stream_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
        )

    async def event_generator():
        from redis.asyncio import Redis  # local import to avoid import cycles

        r: Redis = Redis.from_url(settings.redis_url, decode_responses=True)
        stream_key = f"job:{job_id}:events"
        last_id = from_id

        try:
            # Send a connect acknowledgement so the client knows the stream is live
            yield f"data: {json.dumps({'type': 'stream.connected', 'job_id': job_id})}\n\n"

            while True:
                if await request.is_disconnected():
                    log.debug("stream.client_disconnected", job_id=job_id)
                    break

                # XREAD with a 2-second block timeout so we can check for disconnect
                results = await r.xread(
                    {stream_key: last_id},
                    count=50,
                    block=2000,
                )

                if results:
                    for _stream_name, messages in results:
                        for msg_id, msg_fields in messages:
                            last_id = msg_id
                            raw = msg_fields.get("data", "{}")
                            yield f"data: {raw}\n\n"

                            # Stop streaming when a terminal event arrives
                            try:
                                parsed = json.loads(raw)
                                if parsed.get("type") in _TERMINAL_EVENTS:
                                    yield f"data: {json.dumps({'type': 'stream.end', 'job_id': job_id})}\n\n"
                                    return
                            except json.JSONDecodeError:
                                pass

                # Brief yield to allow other coroutines / disconnect checks
                await asyncio.sleep(0)

        except asyncio.CancelledError:
            log.debug("stream.cancelled", job_id=job_id)
        finally:
            await r.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",    # disable Nginx/Traefik response buffering
            "Connection": "keep-alive",
        },
    )
