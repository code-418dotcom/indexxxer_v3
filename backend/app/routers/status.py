"""
Unified service status endpoint — probes all infrastructure components.

GET /status  →  { services: { name: str, up: bool }[] }
"""

import redis as redis_lib
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

router = APIRouter(tags=["system"])


@router.get("/status")
async def service_status(db: AsyncSession = Depends(get_db)) -> dict:
    services: list[dict] = []

    # ── API (always up if this handler runs) ────────────────────────────────
    services.append({"name": "api", "up": True})

    # ── PostgreSQL ──────────────────────────────────────────────────────────
    try:
        await db.execute(text("SELECT 1"))
        services.append({"name": "database", "up": True})
    except Exception:
        services.append({"name": "database", "up": False})

    # ── Redis ───────────────────────────────────────────────────────────────
    try:
        r = redis_lib.from_url(settings.redis_url, decode_responses=True, socket_timeout=2)
        r.ping()
        services.append({"name": "redis", "up": True})
    except Exception:
        services.append({"name": "redis", "up": False})

    # ── Celery Worker ───────────────────────────────────────────────────────
    try:
        from app.workers.celery_app import celery_app
        inspect = celery_app.control.inspect(timeout=1.5)
        pong = inspect.ping() or {}
        services.append({"name": "worker", "up": len(pong) > 0})
    except Exception:
        services.append({"name": "worker", "up": False})

    # ── Celery Beat (heartbeat key written every 60s with 120s TTL) ────────
    try:
        from app.workers.tasks.heartbeat import HEARTBEAT_KEY
        r2 = redis_lib.from_url(settings.redis_url, decode_responses=True, socket_timeout=2)
        services.append({"name": "beat", "up": bool(r2.exists(HEARTBEAT_KEY))})
    except Exception:
        services.append({"name": "beat", "up": False})

    # ── NSFW Tagger ─────────────────────────────────────────────────────────
    try:
        import httpx
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=2.0)) as client:
            resp = await client.get(f"{settings.nsfw_tagger_url}/ready")
            services.append({"name": "tagger", "up": resp.status_code == 200})
    except Exception:
        services.append({"name": "tagger", "up": False})

    return {"services": services}
