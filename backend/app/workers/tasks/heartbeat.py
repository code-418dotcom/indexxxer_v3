"""Beat heartbeat — writes a Redis key with TTL so the status endpoint can detect beat."""

import redis as redis_lib

from app.config import settings
from app.workers.celery_app import celery_app

HEARTBEAT_KEY = "indexxxer:beat:alive"
HEARTBEAT_TTL = 120  # seconds — beat fires every 60s, so 120s gives 1 missed tick grace


@celery_app.task(
    queue="indexing",
    name="app.workers.tasks.heartbeat.beat_heartbeat_task",
)
def beat_heartbeat_task() -> str:
    r = redis_lib.from_url(settings.redis_url, decode_responses=True)
    r.setex(HEARTBEAT_KEY, HEARTBEAT_TTL, "1")
    return "ok"
