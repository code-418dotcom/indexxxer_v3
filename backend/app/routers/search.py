"""
Search endpoints.

GET /search               — tsvector full-text search with filters
GET /search/suggestions   — filename autocomplete (M2: Typesense prefix)
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import Auth
from app.core.pagination import PaginatedResponse
from app.database import get_db
from app.schemas.media_item import MediaItemSummary
from app.services import search_service

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=PaginatedResponse[MediaItemSummary])
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    type: str | None = Query(None, description="Filter by media_type: image | video"),
    tag_ids: list[str] = Query(default=[], description="Filter by tag IDs (AND logic)"),
    source_id: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    sort: str = Query(default="relevance", description="relevance | date | size | name"),
    order: str = Query(default="desc", description="asc | desc"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    return await search_service.full_text_search(
        db,
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


@router.get("/suggestions", response_model=list[str])
async def suggestions(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=50),
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    return await search_service.get_suggestions(db, q=q, limit=limit)
