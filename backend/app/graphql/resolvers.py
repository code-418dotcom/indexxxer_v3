"""
GraphQL resolver functions — delegate to existing services.
"""

from __future__ import annotations

from typing import Any, Optional

import strawberry
from fastapi import Request
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.types import Info

from app.config import settings
from app.graphql.types import (
    AnalyticsOverviewGQL,
    FaceClusterGQL,
    MediaItemGQL,
    MediaSourceGQL,
    SearchInput,
    SearchResultGQL,
    TagGQL,
)


def _get_db(info: Info) -> AsyncSession:
    """Extract AsyncSession from Strawberry context."""
    return info.context["db"]


def _require_auth(info: Info) -> None:
    """Validate JWT or static token from request headers."""
    request: Request = info.context["request"]
    auth_header = request.headers.get("Authorization", "")
    api_key = request.headers.get("X-API-Token", "")

    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    elif api_key:
        token = api_key

    if not token:
        raise Exception("Not authenticated")

    # Try JWT
    try:
        from app.core.security import decode_token
        payload = decode_token(token)
        if payload.get("type") == "access":
            return
    except JWTError:
        pass

    # Fall back to static token
    if token == settings.api_token:
        return

    raise Exception("Invalid credentials")


def _media_to_gql(item) -> MediaItemGQL:
    from app.services.storage_service import make_thumbnail_url

    tags = []
    for mt in (item.media_tags or []):
        if mt.tag:
            tags.append(TagGQL(id=mt.tag.id, name=mt.tag.name, slug=mt.tag.slug, color=mt.tag.color))

    return MediaItemGQL(
        id=item.id,
        filename=item.filename,
        media_type=item.media_type or "unknown",
        file_path=item.file_path,
        width=item.width,
        height=item.height,
        duration_seconds=item.duration_seconds,
        mime_type=item.mime_type,
        file_size=item.file_size,
        is_favourite=item.is_favourite or False,
        caption=item.caption,
        caption_status=getattr(item, "caption_status", None),
        summary=item.summary,
        face_count=len(item.faces) if hasattr(item, "faces") and item.faces else 0,
        created_at=item.created_at,
        thumbnail_url=make_thumbnail_url(item.id) if item.thumbnail_path else None,
        tags=tags,
    )


async def resolve_media(id: str, info: Info) -> Optional[MediaItemGQL]:
    _require_auth(info)
    db = _get_db(info)
    from app.services import media_service
    from app.services.media_service import WITH_TAGS_AND_FACES
    from sqlalchemy import select
    from app.models.media_item import MediaItem
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(MediaItem)
        .where(MediaItem.id == id)
        .options(*WITH_TAGS_AND_FACES)
    )
    item = result.scalar_one_or_none()
    if not item:
        return None
    return _media_to_gql(item)


async def resolve_search(input: SearchInput, info: Info) -> SearchResultGQL:
    _require_auth(info)
    db = _get_db(info)
    from app.services import search_service

    limit = input.limit or 20
    offset = input.offset or 0
    page = (offset // limit) + 1

    common = dict(q=input.query, media_type=None, tag_ids=None, source_id=None,
                  date_from=None, date_to=None, sort="relevance", order="desc",
                  page=page, limit=limit)

    mode = input.mode or "auto"
    if mode == "semantic":
        result = await search_service.semantic_search(db, **common)
    elif mode == "hybrid":
        result = await search_service.hybrid_search(db, **common)
    elif mode == "text":
        result = await search_service.full_text_search(db, **common)
    else:
        if search_service._should_use_semantic(input.query):
            result = await search_service.semantic_search(db, **common)
        else:
            result = await search_service.full_text_search(db, **common)

    items = []
    for summary in result.items:
        items.append(MediaItemGQL(
            id=summary.id,
            filename=summary.filename,
            media_type=summary.media_type or "unknown",
            file_path=summary.file_path,
            width=summary.width,
            height=summary.height,
            duration_seconds=summary.duration_seconds,
            mime_type=summary.mime_type,
            file_size=summary.file_size,
            is_favourite=summary.is_favourite,
            face_count=summary.face_count,
            created_at=summary.created_at,
            thumbnail_url=summary.thumbnail_url,
        ))
    return SearchResultGQL(items=items, total=result.total)


async def resolve_sources(info: Info) -> list[MediaSourceGQL]:
    _require_auth(info)
    db = _get_db(info)
    from app.services import source_service
    sources = await source_service.list_sources(db)
    return [
        MediaSourceGQL(
            id=s.id, name=s.name, path=s.path,
            source_type=s.source_type, enabled=s.enabled,
            last_scan_at=s.last_scan_at,
        )
        for s in sources
    ]


async def resolve_analytics_overview(info: Info) -> AnalyticsOverviewGQL:
    _require_auth(info)
    db = _get_db(info)
    from app.services import analytics_service
    data = await analytics_service.get_overview(db)
    return AnalyticsOverviewGQL(
        total_media=data["total_media"],
        total_sources=data["source_count"],
        storage_bytes=data["storage_bytes"],
        face_count=data["face_count"],
        cluster_count=data["cluster_count"],
    )


async def resolve_create_tag(name: str, color: Optional[str], info: Info) -> TagGQL:
    _require_auth(info)
    db = _get_db(info)
    import re
    from sqlalchemy import select
    from app.models.tag import Tag

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    existing = (await db.execute(select(Tag).where(Tag.slug == slug))).scalar_one_or_none()
    if existing:
        return TagGQL(id=existing.id, name=existing.name, slug=existing.slug, color=existing.color)

    tag = Tag(name=name, slug=slug, color=color)
    db.add(tag)
    await db.flush()
    await db.refresh(tag)
    return TagGQL(id=tag.id, name=tag.name, slug=tag.slug, color=tag.color)


async def resolve_delete_tag(id: str, info: Info) -> bool:
    _require_auth(info)
    db = _get_db(info)
    from app.models.tag import Tag
    tag = await db.get(Tag, id)
    if not tag:
        return False
    await db.delete(tag)
    await db.flush()
    return True
