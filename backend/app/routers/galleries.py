"""
Gallery endpoints.

GET  /galleries                    — paginated list of galleries
GET  /galleries/{id}               — gallery detail (metadata + image list)
GET  /galleries/{id}/cover         — serve cover JPEG
GET  /galleries/{id}/images/{index} — serve image from ZIP on-the-fly
POST /galleries/scan               — trigger gallery scan for all enabled local sources
"""

import zipfile

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import Auth
from app.database import get_db
from app.models.gallery import Gallery, GalleryImage
from app.schemas.gallery import GalleryDetailSchema, GallerySchema
from app.services import gallery_service

router = APIRouter(tags=["galleries"])

_IMAGE_MIME: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}


@router.get("/galleries", response_model=dict)
async def list_galleries(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=48, ge=1, le=200),
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List all indexed galleries with cover URL and image count."""
    items, total = await gallery_service.list_galleries(
        db, api_v1_prefix=settings.api_v1_prefix, page=page, limit=limit
    )
    pages = (total + limit - 1) // limit
    return {
        "items": [i.model_dump() for i in items],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


@router.get("/galleries/{gallery_id}", response_model=GalleryDetailSchema)
async def get_gallery(
    gallery_id: str = Path(...),
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
) -> GalleryDetailSchema:
    """Return gallery metadata plus the full sorted image list."""
    detail = await gallery_service.get_gallery(
        db, gallery_id=gallery_id, api_v1_prefix=settings.api_v1_prefix
    )
    if not detail:
        raise HTTPException(status_code=404, detail="Gallery not found")
    return detail


@router.get("/galleries/{gallery_id}/cover")
async def get_gallery_cover(
    gallery_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Serve the cover JPEG for a gallery (no auth — used as <img> src)."""
    gallery = await db.get(Gallery, gallery_id)
    if not gallery or not gallery.cover_path:
        raise HTTPException(status_code=404, detail="Cover not found")
    try:
        data = open(gallery.cover_path, "rb").read()
    except OSError:
        raise HTTPException(status_code=404, detail="Cover file missing")
    return Response(content=data, media_type="image/jpeg")


@router.get("/galleries/{gallery_id}/images/{index}")
async def get_gallery_image(
    gallery_id: str = Path(...),
    index: int = Path(..., ge=0),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Serve image *index* (0-based) from the gallery (ZIP or folder, no auth)."""
    from pathlib import Path as FPath
    from sqlalchemy import select

    gallery = await db.get(Gallery, gallery_id)
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")

    result = await db.execute(
        select(GalleryImage)
        .where(GalleryImage.gallery_id == gallery_id, GalleryImage.index_order == index)
    )
    img_entry = result.scalar_one_or_none()
    if not img_entry:
        raise HTTPException(status_code=404, detail="Image not found")

    is_zip = gallery.file_path.lower().endswith(".zip")

    if is_zip:
        try:
            with zipfile.ZipFile(gallery.file_path, "r") as zf:
                data = zf.read(img_entry.filename)
        except (KeyError, zipfile.BadZipFile, OSError):
            raise HTTPException(status_code=404, detail="Image unreadable from ZIP")
    else:
        # Folder gallery — img_entry.filename is the absolute filesystem path
        try:
            data = open(img_entry.filename, "rb").read()
        except OSError:
            raise HTTPException(status_code=404, detail="Image file missing")

    suffix = FPath(img_entry.filename).suffix.lower()
    mime = _IMAGE_MIME.get(suffix, "image/jpeg")
    return Response(content=data, media_type=mime)


@router.post("/galleries/scan", status_code=202)
async def trigger_gallery_scan(
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Enqueue gallery scanning for all enabled local sources."""
    from sqlalchemy import select
    from app.models.media_source import MediaSource

    result = await db.execute(
        select(MediaSource).where(
            MediaSource.enabled == True,  # noqa: E712
            MediaSource.source_type == "local",
        )
    )
    sources = result.scalars().all()

    if not sources:
        return {"status": "no_sources", "queued": 0}

    from app.workers.tasks.gallery import scan_galleries_task

    task_ids = []
    for source in sources:
        task = scan_galleries_task.apply_async(
            kwargs={"source_id": source.id, "path": source.path},
            queue="indexing",
        )
        task_ids.append(task.id)

    return {"status": "queued", "sources": len(sources), "task_ids": task_ids}
