"""
Worker queue management endpoints.

GET    /workers/queues              — queue depths + online workers
POST   /workers/queues/{q}/pause   — stop all workers consuming queue q
POST   /workers/queues/{q}/resume  — re-enable consumption of queue q
DELETE /workers/queues/{q}         — flush (purge) all pending tasks in queue q
"""

from fastapi import APIRouter, Path

import redis as redis_lib

from app.config import settings
from app.core.deps import Auth

router = APIRouter(tags=["workers"])

TRACKED_QUEUES = ["ml", "ai", "indexing", "thumbnails", "hashing"]


def _redis() -> redis_lib.Redis:
    return redis_lib.from_url(settings.celery_broker_url, decode_responses=True)


@router.get("/workers/queues")
async def get_queue_status(_: None = Auth) -> dict:
    """Return queue depths and online worker info."""
    r = _redis()
    depths = {q: r.llen(q) for q in TRACKED_QUEUES}

    from app.workers.celery_app import celery_app
    try:
        inspect = celery_app.control.inspect(timeout=1.5)
        raw_queues = inspect.active_queues() or {}
    except Exception:
        raw_queues = {}

    workers = [
        {
            "name": name,
            "queues": [q["name"] for q in (queues or [])],
        }
        for name, queues in raw_queues.items()
    ]

    return {"depths": depths, "workers": workers}


@router.post("/workers/queues/{queue}/pause")
async def pause_queue(queue: str = Path(...), _: None = Auth) -> dict:
    """Stop only the workers that are currently consuming this queue."""
    from app.workers.celery_app import celery_app
    try:
        inspect = celery_app.control.inspect(timeout=1.5)
        raw = inspect.active_queues() or {}
    except Exception:
        raw = {}
    # Only cancel on workers that are actually consuming this queue
    targets = [
        name for name, queues in raw.items()
        if any(q["name"] == queue for q in (queues or []))
    ]
    if targets:
        celery_app.control.cancel_consumer(queue, destination=targets)
    return {"status": "paused", "queue": queue, "targets": targets}


@router.post("/workers/queues/{queue}/resume")
async def resume_queue(queue: str = Path(...), _: None = Auth) -> dict:
    """Resume consumption — only on workers whose hostname indicates they own this queue.

    The ml queue belongs exclusively to gpu_worker instances.
    All other queues are resumed on all online workers.
    """
    from app.workers.celery_app import celery_app
    try:
        inspect = celery_app.control.inspect(timeout=1.5)
        raw = inspect.active_queues() or {}
    except Exception:
        raw = {}
    online = list(raw.keys())
    if queue == "ml":
        # Only resume on GPU workers — never let the regular worker pull ml tasks
        targets = [w for w in online if "gpu_worker" in w]
    else:
        targets = online
    if targets:
        celery_app.control.add_consumer(queue, destination=targets)
    return {"status": "resumed", "queue": queue, "targets": targets}


@router.delete("/workers/queues/{queue}")
async def flush_queue(queue: str = Path(...), _: None = Auth) -> dict:
    """Delete the queue key — removes all pending tasks instantly."""
    r = _redis()
    count = int(r.llen(queue))
    r.delete(queue)
    return {"status": "flushed", "queue": queue, "count": count}
