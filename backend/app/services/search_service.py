"""
Search service — M2.

Text path:   tsvector match → pg_trgm fuzzy fallback
Semantic path: CLIP text→embedding → pgvector cosine distance
Auto-detect: ≤2 words → text; ≥3 words → semantic (overridable via mode param)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, literal, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PaginationParams, paginate
from app.models.media_item import MediaItem
from app.models.tag import MediaTag
from app.services.media_service import WITH_TAGS_AND_FACES, to_media_summary


# ── Mode detection ─────────────────────────────────────────────────────────────

def _should_use_semantic(q: str) -> bool:
    """Auto-detect: ≥3 words or >30 chars → semantic CLIP search."""
    stripped = q.strip()
    return len(stripped.split()) >= 3 or len(stripped) > 30


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
        .options(*WITH_TAGS_AND_FACES)
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
        .options(*WITH_TAGS_AND_FACES)
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


# ── Semantic search (CLIP) ─────────────────────────────────────────────────────

async def semantic_search(
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
    """Encode query with CLIP text encoder and return nearest neighbours."""
    params = PaginationParams(page=page, limit=limit)

    try:
        embedding = _encode_text_query(q)
    except Exception:
        # CLIP not available — fall back to text search
        return await full_text_search(
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

    try:
        from pgvector.sqlalchemy import Vector

        query_vec = literal(embedding, type_=Vector(768))
    except ImportError:
        return await full_text_search(
            db, q=q, media_type=media_type, tag_ids=tag_ids,
            source_id=source_id, date_from=date_from, date_to=date_to,
            sort=sort, order=order, page=page, limit=limit,
        )

    distance = MediaItem.clip_embedding.op("<=>")(query_vec)

    stmt = (
        select(MediaItem)
        .options(*WITH_TAGS_AND_FACES)
        .where(MediaItem.clip_status == "done")
        .where(MediaItem.clip_embedding.isnot(None))
    )
    stmt = _apply_common_filters(
        stmt,
        media_type=media_type,
        source_id=source_id,
        tag_ids=tag_ids,
        date_from=date_from,
        date_to=date_to,
    )
    # Always order by cosine distance for semantic; other sort fields apply on tie
    stmt = stmt.order_by(distance)

    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()

    items = (
        await db.execute(stmt.offset(params.offset).limit(params.limit))
    ).scalars().all()

    return paginate([to_media_summary(i) for i in items], total, params)


def _encode_text_query(q: str) -> list[float]:
    """Encode a text query with CLIP and return a unit-normalised 768-dim vector."""
    from app.ml.clip_model import get_clip_model
    import torch

    model, _, tokenizer = get_clip_model()
    tokens = tokenizer([q])
    with torch.no_grad():
        feat = model.encode_text(tokens)
        feat = feat / feat.norm(dim=-1, keepdim=True)
    return feat[0].cpu().numpy().tolist()


# ── Hybrid search (RRF fusion) ─────────────────────────────────────────────────

async def hybrid_search(
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
    """Reciprocal Rank Fusion of text + semantic results."""
    params = PaginationParams(page=page, limit=limit)
    fetch_n = min(200, limit * 4)  # fetch more from each pass for RRF

    # Run both passes with large window
    text_res = await full_text_search(
        db, q=q, media_type=media_type, tag_ids=tag_ids,
        source_id=source_id, date_from=date_from, date_to=date_to,
        sort=sort, order=order, page=1, limit=fetch_n,
    )
    sem_res = await semantic_search(
        db, q=q, media_type=media_type, tag_ids=tag_ids,
        source_id=source_id, date_from=date_from, date_to=date_to,
        sort=sort, order=order, page=1, limit=fetch_n,
    )

    # Reciprocal Rank Fusion (k=60 is standard)
    k = 60
    scores: dict[str, float] = {}
    items_by_id: dict[str, object] = {}

    for rank, item in enumerate(text_res["items"]):
        scores[item.id] = scores.get(item.id, 0.0) + 1.0 / (k + rank + 1)
        items_by_id[item.id] = item

    for rank, item in enumerate(sem_res["items"]):
        scores[item.id] = scores.get(item.id, 0.0) + 1.0 / (k + rank + 1)
        items_by_id[item.id] = item

    ranked = sorted(scores.keys(), key=lambda i: scores[i], reverse=True)
    total = len(ranked)
    page_ids = ranked[params.offset: params.offset + params.limit]
    page_items = [items_by_id[i] for i in page_ids]

    return paginate(page_items, total, params)


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
