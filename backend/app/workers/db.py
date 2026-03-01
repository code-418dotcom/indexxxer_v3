"""
Task-safe database session for Celery workers.

Celery tasks (prefork) are synchronous. We wrap async SQLAlchemy operations
with asyncio.run(), creating a fresh event loop per call. NullPool prevents
connection leaks across forked worker processes.

Usage:
    import asyncio
    from app.workers.db import task_session

    def my_task(item_id: str):
        asyncio.run(_async_body(item_id))

    async def _async_body(item_id: str):
        async with task_session() as session:
            obj = await session.get(MyModel, item_id)
            ...
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings

# NullPool: no connection reuse across tasks — correct for prefork workers
# where connections cannot be shared between processes.
_task_engine = create_async_engine(
    settings.database_url,
    poolclass=NullPool,
    echo=False,
)
_TaskSession = async_sessionmaker(
    bind=_task_engine,
    expire_on_commit=False,
    autoflush=False,
)


@asynccontextmanager
async def task_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager that yields a DB session with auto-commit/rollback."""
    async with _TaskSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
