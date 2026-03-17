"""
Analytics aggregation queries.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media_item import MediaItem
from app.models.media_source import MediaSource
from app.models.query_log import QueryLog


async def get_overview(db: AsyncSession) -> dict:
    """Return high-level platform stats."""
    # Total media count
    total_media = (await db.execute(select(func.count()).select_from(MediaItem))).scalar_one()

    # By index status
    status_rows = await db.execute(
        select(MediaItem.index_status, func.count()).group_by(MediaItem.index_status)
    )
    status_counts: dict[str, int] = {row[0]: row[1] for row in status_rows}

    # Storage bytes
    storage_bytes = (
        await db.execute(select(func.coalesce(func.sum(MediaItem.file_size), 0)))
    ).scalar_one()

    # Source count
    source_count = (await db.execute(select(func.count()).select_from(MediaSource))).scalar_one()

    return {
        "total_media": total_media,
        "indexed": status_counts.get("indexed", 0),
        "pending": status_counts.get("pending", 0) + status_counts.get("thumbnailing", 0),
        "error": status_counts.get("error", 0),
        "storage_bytes": int(storage_bytes),
        "source_count": source_count,
    }


async def get_search_stats(db: AsyncSession, days: int = 30) -> dict:
    """Return search query analytics for the last N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Daily query counts
    daily_rows = await db.execute(
        text(
            """
            SELECT DATE(created_at) AS day, COUNT(*) AS cnt
            FROM query_logs
            WHERE created_at >= :since
            GROUP BY day
            ORDER BY day
            """
        ),
        {"since": since},
    )
    daily = [{"date": str(r.day), "count": r.cnt} for r in daily_rows]

    # Top queries
    top_rows = await db.execute(
        text(
            """
            SELECT query, COUNT(*) AS cnt
            FROM query_logs
            WHERE created_at >= :since AND query IS NOT NULL
            GROUP BY query
            ORDER BY cnt DESC
            LIMIT 10
            """
        ),
        {"since": since},
    )
    top_queries = [{"query": r.query, "count": r.cnt} for r in top_rows]

    # Mode breakdown
    mode_rows = await db.execute(
        text(
            """
            SELECT search_mode, COUNT(*) AS cnt
            FROM query_logs
            WHERE created_at >= :since
            GROUP BY search_mode
            """
        ),
        {"since": since},
    )
    mode_breakdown = {r.search_mode: r.cnt for r in mode_rows}

    total = (
        await db.execute(
            select(func.count())
            .select_from(QueryLog)
            .where(QueryLog.created_at >= since)
        )
    ).scalar_one()

    return {
        "daily": daily,
        "top_queries": top_queries,
        "mode_breakdown": mode_breakdown,
        "total_searches": total,
    }


async def get_indexing_stats(db: AsyncSession, days: int = 30) -> dict:
    """Return indexing history for the last N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    daily_rows = await db.execute(
        text(
            """
            SELECT DATE(indexed_at) AS day, COUNT(*) AS cnt
            FROM media_items
            WHERE indexed_at >= :since
            GROUP BY day
            ORDER BY day
            """
        ),
        {"since": since},
    )
    daily = [{"date": str(r.day), "count": r.cnt} for r in daily_rows]

    # Avg latency from query_logs
    avg_latency = (
        await db.execute(
            select(func.avg(QueryLog.latency_ms)).where(QueryLog.created_at >= since)
        )
    ).scalar_one()

    error_count = (
        await db.execute(
            select(func.count())
            .select_from(MediaItem)
            .where(MediaItem.index_status == "error", MediaItem.indexed_at >= since)
        )
    ).scalar_one()

    return {
        "daily_indexed": daily,
        "avg_search_latency_ms": round(avg_latency or 0, 1),
        "error_count": error_count,
    }
