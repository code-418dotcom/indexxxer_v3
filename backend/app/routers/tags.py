"""
Tag CRUD endpoints + GET /tags/{tag_id}/media.
"""

import re

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import Auth
from app.core.exceptions import conflict, not_found
from app.core.pagination import PaginatedResponse, PaginationParams, paginate
from app.database import get_db
from app.models.tag import Tag
from app.schemas.media_item import MediaItemSummary
from app.schemas.tag import TagCreate, TagResponse, TagUpdate
from app.services import media_service

router = APIRouter(prefix="/tags", tags=["tags"])


def _slugify(name: str) -> str:
    """Convert tag name to a URL-safe slug (e.g. "Jane Doe" → "jane-doe")."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


@router.get("", response_model=PaginatedResponse[TagResponse])
async def list_tags(
    category: str | None = Query(None),
    q: str | None = Query(None, description="Name substring filter"),
    params: PaginationParams = Depends(),
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Tag)
    if category:
        stmt = stmt.where(Tag.category == category)
    if q:
        stmt = stmt.where(Tag.name.ilike(f"%{q}%"))
    stmt = stmt.order_by(Tag.name)

    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    tags = (
        await db.execute(stmt.offset(params.offset).limit(params.limit))
    ).scalars().all()

    return paginate([TagResponse.model_validate(t) for t in tags], total, params)


@router.post("", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(
    body: TagCreate,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    slug = _slugify(body.name)
    existing = (
        await db.execute(select(Tag).where(Tag.slug == slug))
    ).scalar_one_or_none()
    if existing:
        raise conflict(f"Tag with slug '{slug}' already exists")

    tag = Tag(name=body.name, slug=slug, category=body.category, color=body.color)
    db.add(tag)
    await db.flush()
    await db.refresh(tag)
    return TagResponse.model_validate(tag)


@router.post("/ai/backfill")
async def backfill_ai_tags(
    _: None = Auth,
):
    """Trigger NSFW AI tagging for all media items that don't have AI tags yet."""
    from app.workers.tasks.nsfw_tag import backfill_nsfw_tags_task

    result = backfill_nsfw_tags_task.apply_async(queue="ai")
    return {"task_id": result.id, "status": "dispatched"}


@router.get("/{tag_id}", response_model=TagResponse)
async def get_tag(
    tag_id: str,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    tag = await db.get(Tag, tag_id)
    if not tag:
        raise not_found("Tag", tag_id)
    return TagResponse.model_validate(tag)


@router.put("/{tag_id}", response_model=TagResponse)
async def update_tag(
    tag_id: str,
    body: TagUpdate,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    tag = await db.get(Tag, tag_id)
    if not tag:
        raise not_found("Tag", tag_id)

    if body.name is not None:
        tag.name = body.name
        tag.slug = _slugify(body.name)
    if body.category is not None:
        tag.category = body.category
    if body.color is not None:
        tag.color = body.color

    await db.flush()
    await db.refresh(tag)
    return TagResponse.model_validate(tag)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: str,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    tag = await db.get(Tag, tag_id)
    if not tag:
        raise not_found("Tag", tag_id)
    await db.delete(tag)
    await db.flush()


@router.get("/{tag_id}/media", response_model=PaginatedResponse[MediaItemSummary])
async def get_tag_media(
    tag_id: str,
    params: PaginationParams = Depends(),
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    """Return all media items that carry this tag (paginated)."""
    # Verify tag exists first
    tag = await db.get(Tag, tag_id)
    if not tag:
        raise not_found("Tag", tag_id)
    return await media_service.list_media(db, params, tag_ids=[tag_id])
