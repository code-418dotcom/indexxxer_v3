from __future__ import annotations

from pathlib import PurePosixPath

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.gallery import Gallery, GalleryImage
from app.models.performer import Performer
from app.schemas.gallery import GalleryDetailSchema, GalleryImageSchema, GallerySchema
from app.services.performer_service import _build_match_patterns, _name_matches


def _cover_url(gallery: Gallery, api_v1_prefix: str) -> str | None:
    if gallery.cover_path:
        return f"{api_v1_prefix}/galleries/{gallery.id}/cover"
    return None


def _to_schema(gallery: Gallery, api_v1_prefix: str) -> GallerySchema:
    return GallerySchema(
        id=gallery.id,
        source_id=gallery.source_id,
        filename=gallery.filename,
        file_path=gallery.file_path,
        image_count=gallery.image_count,
        file_size=gallery.file_size,
        file_mtime=gallery.file_mtime.isoformat() if gallery.file_mtime else None,
        cover_url=_cover_url(gallery, api_v1_prefix),
        created_at=gallery.created_at.isoformat(),
        updated_at=gallery.updated_at.isoformat(),
    )


async def list_galleries(
    db: AsyncSession,
    api_v1_prefix: str,
    page: int = 1,
    limit: int = 48,
) -> tuple[list[GallerySchema], int]:
    offset = (page - 1) * limit

    total_result = await db.execute(select(func.count()).select_from(Gallery))
    total = total_result.scalar_one()

    result = await db.execute(
        select(Gallery)
        .order_by(Gallery.filename)
        .offset(offset)
        .limit(limit)
    )
    galleries = result.scalars().all()

    return [_to_schema(g, api_v1_prefix) for g in galleries], total


async def list_galleries_for_performer(
    db: AsyncSession,
    performer_id: str,
    api_v1_prefix: str,
    page: int = 1,
    limit: int = 48,
) -> tuple[list[GallerySchema], int]:
    """Find galleries whose file_path matches a performer's name or aliases."""
    performer = await db.get(Performer, performer_id)
    if not performer:
        return [], 0

    patterns = _build_match_patterns(performer)
    if not patterns:
        return [], 0

    # Load all galleries and filter in Python (same approach as media matching)
    result = await db.execute(select(Gallery).order_by(Gallery.filename))
    all_galleries = result.scalars().all()

    matched = []
    for g in all_galleries:
        parts = PurePosixPath(g.file_path).parts
        for part in parts:
            found = False
            for pattern in patterns:
                if _name_matches(pattern, part):
                    matched.append(g)
                    found = True
                    break
            if found:
                break

    total = len(matched)
    offset = (page - 1) * limit
    page_items = matched[offset : offset + limit]

    return [_to_schema(g, api_v1_prefix) for g in page_items], total


async def get_gallery(
    db: AsyncSession,
    gallery_id: str,
    api_v1_prefix: str,
) -> GalleryDetailSchema | None:
    result = await db.execute(
        select(Gallery)
        .options(selectinload(Gallery.images))
        .where(Gallery.id == gallery_id)
    )
    gallery = result.scalar_one_or_none()
    if not gallery:
        return None

    images = [
        GalleryImageSchema(
            id=img.id,
            gallery_id=img.gallery_id,
            filename=img.filename,
            index_order=img.index_order,
            width=img.width,
            height=img.height,
        )
        for img in sorted(gallery.images, key=lambda i: i.index_order)
    ]

    return GalleryDetailSchema(
        id=gallery.id,
        source_id=gallery.source_id,
        filename=gallery.filename,
        file_path=gallery.file_path,
        image_count=gallery.image_count,
        file_size=gallery.file_size,
        file_mtime=gallery.file_mtime.isoformat() if gallery.file_mtime else None,
        cover_url=_cover_url(gallery, api_v1_prefix),
        created_at=gallery.created_at.isoformat(),
        updated_at=gallery.updated_at.isoformat(),
        images=images,
    )
