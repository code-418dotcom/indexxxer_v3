"""
Search service — text search only.

Text path:   tsvector match → pg_trgm fuzzy fallback
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PaginationParams, paginate
from app.models.media_item import MediaItem
from app.models.tag import MediaTag
from app.services.media_service import WITH_TAGS_AND_PERFORMERS, to_media_summary


# ── Shared filter helpers ──────────────────────────────────────────────────────

def _apply_common_filters(
    stmt,
    *,
    media_type: str | None,
    source_id: str | None,
    tag_ids: list[str] | None,
    date_from: datetime | None,
    date_to: datetime | None,
):
    if media_type:
        stmt = stmt.where(MediaItem.media_type == media_type)
    if source_id:
        stmt = stmt.where(MediaItem.source_id == source_id)
    if tag_ids:
        for tid in tag_ids:
            stmt = stmt.where(
                MediaItem.id.in_(
                    select(MediaTag.media_id).where(MediaTag.tag_id == tid)
                )
            )
    if date_from:
        stmt = stmt.where(MediaItem.indexed_at >= date_from)
    if date_to:
        stmt = stmt.where(MediaItem.indexed_at <= date_to)
    return stmt


def _apply_sort(stmt, sort: str, order: str, ts_query=None):
    if sort == "relevance" and ts_query is not None:
        rank = func.ts_rank(MediaItem.search_vector, ts_query)
        return stmt.order_by(rank.desc() if order == "desc" else rank.asc())
    elif sort == "date":
        col = MediaItem.indexed_at
        return stmt.order_by(col.desc() if order == "desc" else col.asc())
    elif sort == "size":
        col = MediaItem.file_size
        return stmt.order_by(
            col.desc().nulls_last() if order == "desc" else col.asc().nulls_last()
        )
    elif sort == "name":
        col = MediaItem.filename
        return stmt.order_by(col.asc() if order == "asc" else col.desc())
    return stmt


# ── Full-text search (tsvector + pg_trgm fallback) ────────────────────────────

async def full_text_search(
    db: AsyncSession,
    *,
    q: str,
    media_type: str | None = None,
    tag_ids: list[str] | None = None,
    source_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort: str = "relevance",
    order: str = "desc",
    page: int = 1,
    limit: int = 50,
) -> dict:
    params = PaginationParams(page=page, limit=limit)
    ts_query = func.websearch_to_tsquery("english", q)

    # Primary: tsvector match
    stmt = (
        select(MediaItem)
        .options(*WITH_TAGS_AND_PERFORMERS)
        .where(MediaItem.search_vector.op("@@")(ts_query))
    )
    stmt = _apply_common_filters(
        stmt,
        media_type=media_type,
        source_id=source_id,
        tag_ids=tag_ids,
        date_from=date_from,
        date_to=date_to,
    )
    stmt = _apply_sort(stmt, sort, order, ts_query)

    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()

    # Fallback to pg_trgm similarity when tsvector returns nothing
    if total == 0:
        return await fuzzy_text_search(
            db,
            q=q,
            media_type=media_type,
            tag_ids=tag_ids,
            source_id=source_id,
            date_from=date_from,
            date_to=date_to,
            sort=sort,
            order=order,
            page=page,
            limit=limit,
        )

    items = (
        await db.execute(stmt.offset(params.offset).limit(params.limit))
    ).scalars().all()

    return paginate([to_media_summary(i) for i in items], total, params)


# ── pg_trgm fuzzy search ───────────────────────────────────────────────────────

async def fuzzy_text_search(
    db: AsyncSession,
    *,
    q: str,
    media_type: str | None = None,
    tag_ids: list[str] | None = None,
    source_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort: str = "relevance",
    order: str = "desc",
    page: int = 1,
    limit: int = 50,
) -> dict:
    params = PaginationParams(page=page, limit=limit)
    sim = func.similarity(MediaItem.filename, q)

    stmt = (
        select(MediaItem)
        .options(*WITH_TAGS_AND_PERFORMERS)
        .where(sim > 0.3)
    )
    stmt = _apply_common_filters(
        stmt,
        media_type=media_type,
        source_id=source_id,
        tag_ids=tag_ids,
        date_from=date_from,
        date_to=date_to,
    )

    if sort == "relevance":
        stmt = stmt.order_by(sim.desc() if order == "desc" else sim.asc())
    else:
        stmt = _apply_sort(stmt, sort, order)

    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()

    items = (
        await db.execute(stmt.offset(params.offset).limit(params.limit))
    ).scalars().all()

    return paginate([to_media_summary(i) for i in items], total, params)


# ── Autocomplete suggestions ───────────────────────────────────────────────────

async def get_suggestions(
    db: AsyncSession,
    *,
    q: str,
    limit: int = 10,
) -> list[str]:
    """Filename-based autocomplete via ILIKE."""
    stmt = (
        select(MediaItem.filename)
        .where(MediaItem.filename.ilike(f"%{q}%"))
        .order_by(MediaItem.filename)
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())
