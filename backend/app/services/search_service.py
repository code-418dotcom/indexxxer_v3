"""
Full-text search service (M1: PostgreSQL tsvector / websearch_to_tsquery).

M2 swap point: replace with Typesense client calls.
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PaginationParams, paginate
from app.models.media_item import MediaItem
from app.models.tag import MediaTag
from app.services.media_service import WITH_TAGS, to_media_summary


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

    stmt = (
        select(MediaItem)
        .options(*WITH_TAGS)
        .where(MediaItem.search_vector.op("@@")(ts_query))
    )

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

    # Sorting
    if sort == "relevance":
        rank = func.ts_rank(MediaItem.search_vector, ts_query)
        stmt = stmt.order_by(rank.desc() if order == "desc" else rank.asc())
    elif sort == "date":
        col = MediaItem.indexed_at
        stmt = stmt.order_by(col.desc() if order == "desc" else col.asc())
    elif sort == "size":
        col = MediaItem.file_size
        stmt = stmt.order_by(
            col.desc().nulls_last() if order == "desc" else col.asc().nulls_last()
        )
    elif sort == "name":
        col = MediaItem.filename
        stmt = stmt.order_by(col.asc() if order == "asc" else col.desc())

    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()

    items = (
        await db.execute(stmt.offset(params.offset).limit(params.limit))
    ).scalars().all()

    return paginate([to_media_summary(i) for i in items], total, params)


async def get_suggestions(
    db: AsyncSession,
    *,
    q: str,
    limit: int = 10,
) -> list[str]:
    """
    Filename-based autocomplete via ILIKE.
    M2 replacement: Typesense prefix search.
    """
    stmt = (
        select(MediaItem.filename)
        .where(MediaItem.filename.ilike(f"%{q}%"))
        .order_by(MediaItem.filename)
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())
