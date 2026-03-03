"""
Media item CRUD service.

All DB access is async. Routers import these functions directly.
Tag eager-loading uses selectinload (two queries: media_items + media_tags + tags).
"""

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import not_found
from app.core.pagination import PaginationParams, paginate
from app.models.media_face import MediaFace
from app.models.media_item import MediaItem
from app.models.tag import MediaTag, Tag
from app.schemas.media_item import (
    BulkActionRequest,
    BulkResult,
    MediaItemDetail,
    MediaItemPatch,
    MediaItemSummary,
)
from app.schemas.tag import TagRef
from app.services.storage_service import make_thumbnail_url

log = structlog.get_logger(__name__)

# Reusable eager-load option: media_items → media_tags → tags
WITH_TAGS = [selectinload(MediaItem.media_tags).selectinload(MediaTag.tag)]
# Includes face rows for face_count
WITH_TAGS_AND_FACES = [
    selectinload(MediaItem.media_tags).selectinload(MediaTag.tag),
    selectinload(MediaItem.faces),
]


# ── Conversion helpers ──────────────────────────────────────────────────────────

def _build_tag_refs(media_tags: list[MediaTag]) -> list[TagRef]:
    return [
        TagRef(
            id=mt.tag.id,
            name=mt.tag.name,
            slug=mt.tag.slug,
            category=mt.tag.category,
            color=mt.tag.color,
            confidence=mt.confidence,
            source=mt.source,
        )
        for mt in media_tags
        if mt.tag is not None
    ]


def to_media_summary(item: MediaItem) -> MediaItemSummary:
    # faces is loaded via selectinload; use len() if available, else 0
    try:
        face_count = len(item.faces)
    except Exception:
        face_count = 0
    return MediaItemSummary(
        id=item.id,
        source_id=item.source_id,
        filename=item.filename,
        file_path=item.file_path,
        media_type=item.media_type,
        mime_type=item.mime_type,
        width=item.width,
        height=item.height,
        duration_seconds=item.duration_seconds,
        file_size=item.file_size,
        thumbnail_url=make_thumbnail_url(item.id) if item.thumbnail_path else None,
        tags=_build_tag_refs(item.media_tags),
        index_status=item.index_status,
        indexed_at=item.indexed_at,
        is_favourite=item.is_favourite,
        clip_status=item.clip_status,
        caption=item.caption,
        caption_status=item.caption_status,
        transcript_status=item.transcript_status,
        summary_status=item.summary_status,
        face_count=face_count,
    )


def to_media_detail(item: MediaItem) -> MediaItemDetail:
    summary = to_media_summary(item)
    return MediaItemDetail(
        **summary.model_dump(),
        bitrate=item.bitrate,
        codec=item.codec,
        frame_rate=item.frame_rate,
        file_hash=item.file_hash,
        file_mtime=item.file_mtime,
        index_error=item.index_error,
        created_at=item.created_at,
        updated_at=item.updated_at,
        transcript=item.transcript,
        summary=item.summary,
    )


async def get_similar_items(
    db: AsyncSession,
    item_id: str,
    limit: int = 12,
) -> list[MediaItemSummary]:
    """Return the *limit* most visually similar items using CLIP cosine distance."""
    item = await db.get(MediaItem, item_id)
    if not item or item.clip_embedding is None:
        return []

    try:
        from pgvector.sqlalchemy import Vector
        from sqlalchemy import literal

        query_vec = literal(item.clip_embedding, type_=Vector(768))
        distance = MediaItem.clip_embedding.op("<=>")(query_vec)

        stmt = (
            select(MediaItem)
            .options(*WITH_TAGS)
            .where(MediaItem.id != item_id)
            .where(MediaItem.clip_status == "done")
            .where(MediaItem.clip_embedding.isnot(None))
            .order_by(distance)
            .limit(limit)
        )
        rows = (await db.execute(stmt)).scalars().all()
        return [to_media_summary(r) for r in rows]
    except Exception:
        return []


# ── Sort helpers ────────────────────────────────────────────────────────────────

_SORT_COLS = {
    "date": MediaItem.indexed_at,
    "name": MediaItem.filename,
    "size": MediaItem.file_size,
    "mtime": MediaItem.file_mtime,
}


def _apply_sort(stmt, sort: str, order: str):
    col = _SORT_COLS.get(sort, MediaItem.indexed_at)
    return stmt.order_by(
        col.asc().nulls_last() if order == "asc" else col.desc().nulls_last()
    )


# ── Service functions ───────────────────────────────────────────────────────────

async def list_media(
    db: AsyncSession,
    params: PaginationParams,
    *,
    media_type: str | None = None,
    source_id: str | None = None,
    tag_ids: list[str] | None = None,
    status: str | None = None,
    favourite: bool | None = None,
    sort: str = "date",
    order: str = "desc",
) -> dict:
    stmt = select(MediaItem).options(*WITH_TAGS_AND_FACES)

    if media_type:
        stmt = stmt.where(MediaItem.media_type == media_type)
    if source_id:
        stmt = stmt.where(MediaItem.source_id == source_id)
    if status:
        stmt = stmt.where(MediaItem.index_status == status)
    if favourite is not None:
        stmt = stmt.where(MediaItem.is_favourite == favourite)
    if tag_ids:
        for tid in tag_ids:
            stmt = stmt.where(
                MediaItem.id.in_(
                    select(MediaTag.media_id).where(MediaTag.tag_id == tid)
                )
            )

    stmt = _apply_sort(stmt, sort, order)

    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()

    items = (
        await db.execute(stmt.offset(params.offset).limit(params.limit))
    ).scalars().all()

    return paginate([to_media_summary(i) for i in items], total, params)


async def get_media_item(db: AsyncSession, item_id: str) -> MediaItemDetail:
    stmt = select(MediaItem).options(*WITH_TAGS_AND_FACES).where(MediaItem.id == item_id)
    item = (await db.execute(stmt)).scalar_one_or_none()
    if not item:
        raise not_found("MediaItem", item_id)
    return to_media_detail(item)


async def get_media_item_orm(db: AsyncSession, item_id: str) -> MediaItem:
    """Return the raw ORM object (for file-serving routes that need file_path/thumbnail_path)."""
    item = await db.get(MediaItem, item_id)
    if not item:
        raise not_found("MediaItem", item_id)
    return item


async def patch_media_item(
    db: AsyncSession, item_id: str, patch: MediaItemPatch
) -> MediaItemDetail:
    stmt = select(MediaItem).options(*WITH_TAGS_AND_FACES).where(MediaItem.id == item_id)
    item = (await db.execute(stmt)).scalar_one_or_none()
    if not item:
        raise not_found("MediaItem", item_id)

    if patch.filename is not None:
        item.filename = patch.filename

    if patch.is_favourite is not None:
        item.is_favourite = patch.is_favourite

    if patch.tags:
        for op in patch.tags:
            if op.op == "add":
                tag = await db.get(Tag, op.id)
                if tag and not await db.get(MediaTag, (item_id, op.id)):
                    db.add(MediaTag(media_id=item_id, tag_id=op.id))
            elif op.op == "remove":
                existing = await db.get(MediaTag, (item_id, op.id))
                if existing:
                    await db.delete(existing)

    await db.flush()

    # Re-fetch with updated tags and faces
    item = (
        await db.execute(
            select(MediaItem).options(*WITH_TAGS_AND_FACES).where(MediaItem.id == item_id)
        )
    ).scalar_one()
    return to_media_detail(item)


async def delete_media_item(db: AsyncSession, item_id: str) -> None:
    """Remove the index entry. Does NOT delete the file from disk."""
    item = await db.get(MediaItem, item_id)
    if not item:
        raise not_found("MediaItem", item_id)
    await db.delete(item)
    await db.flush()


async def bulk_action(db: AsyncSession, req: BulkActionRequest) -> BulkResult:
    processed = 0
    failed = 0
    errors: list[str] = []

    if req.action == "delete":
        for item_id in req.ids:
            try:
                await delete_media_item(db, item_id)
                processed += 1
            except Exception as exc:
                failed += 1
                errors.append(f"{item_id}: {exc}")

    elif req.action in ("add_tags", "remove_tags"):
        tag_ids: list[str] = (req.payload or {}).get("tag_ids", [])
        for item_id in req.ids:
            try:
                item = await db.get(MediaItem, item_id)
                if not item:
                    raise ValueError("not found")
                for tid in tag_ids:
                    if req.action == "add_tags":
                        tag = await db.get(Tag, tid)
                        if tag and not await db.get(MediaTag, (item_id, tid)):
                            db.add(MediaTag(media_id=item_id, tag_id=tid))
                    else:
                        existing = await db.get(MediaTag, (item_id, tid))
                        if existing:
                            await db.delete(existing)
                processed += 1
            except Exception as exc:
                failed += 1
                errors.append(f"{item_id}: {exc}")

        await db.flush()

    return BulkResult(processed=processed, failed=failed, errors=errors)
