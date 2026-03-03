"""
Analytics tasks — lightweight query logging.
Runs on the regular worker (indexing queue).
"""

from __future__ import annotations

import asyncio

from app.workers.celery_app import celery_app
from app.workers.db import task_session


@celery_app.task(
    queue="indexing",
    name="app.workers.tasks.analytics.log_query_task",
)
def log_query_task(
    query: str,
    search_mode: str,
    result_count: int,
    latency_ms: int,
    user_id: str | None = None,
) -> None:
    asyncio.run(_log_query(query, search_mode, result_count, latency_ms, user_id))


async def _log_query(
    query: str,
    search_mode: str,
    result_count: int,
    latency_ms: int,
    user_id: str | None,
) -> None:
    from app.models.query_log import QueryLog

    async with task_session() as session:
        log_entry = QueryLog(
            query=query,
            search_mode=search_mode,
            result_count=result_count,
            latency_ms=latency_ms,
            user_id=user_id,
        )
        session.add(log_entry)
        await session.flush()
