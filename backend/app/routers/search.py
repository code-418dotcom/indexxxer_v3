"""
Search endpoints.

GET /search               — text / semantic / hybrid / auto-detect search
GET /search/suggestions   — filename autocomplete

mode param:
  auto     (default) — ≤2 words → text, ≥3 words → semantic
  text     — force full-text (tsvector + pg_trgm fallback)
  semantic — force CLIP semantic
  hybrid   — Reciprocal Rank Fusion of both
"""

import time
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import Auth
from app.core.pagination import PaginatedResponse
from app.database import get_db
from app.models.user import User
from app.schemas.media_item import MediaItemSummary
from app.services import search_service

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=PaginatedResponse[MediaItemSummary])
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    mode: str = Query(
        default="auto",
        description="Search mode: auto | text | semantic | hybrid",
    ),
    type: str | None = Query(None, description="Filter by media_type: image | video"),
    tag_ids: list[str] = Query(default=[], description="Filter by tag IDs (AND logic)"),
    source_id: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    sort: str = Query(default="relevance", description="relevance | date | size | name"),
    order: str = Query(default="desc", description="asc | desc"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Auth,
    db: AsyncSession = Depends(get_db),
):
    start_ms = time.monotonic()
    common = dict(
        q=q,
        media_type=type,
        tag_ids=tag_ids or None,
        source_id=source_id,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        order=order,
        page=page,
        limit=limit,
    )

    actual_mode = mode
    if mode == "semantic":
        result = await search_service.semantic_search(db, **common)
    elif mode == "hybrid":
        result = await search_service.hybrid_search(db, **common)
    elif mode == "text":
        result = await search_service.full_text_search(db, **common)
    else:
        # auto: pick based on query length
        if search_service._should_use_semantic(q):
            actual_mode = "semantic"
            result = await search_service.semantic_search(db, **common)
        else:
            actual_mode = "text"
            result = await search_service.full_text_search(db, **common)

    latency_ms = int((time.monotonic() - start_ms) * 1000)
    result_count = result.total if hasattr(result, "total") else 0
    user_id = current_user.id if current_user else None

    from app.workers.tasks.analytics import log_query_task
    log_query_task.apply_async(
        kwargs={
            "query": q,
            "search_mode": actual_mode,
            "result_count": result_count,
            "latency_ms": latency_ms,
            "user_id": user_id,
        },
        queue="indexing",
    )

    return result


@router.get("/suggestions", response_model=list[str])
async def suggestions(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=50),
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    return await search_service.get_suggestions(db, q=q, limit=limit)
