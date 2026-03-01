"""
Media item endpoints.

Route order matters: POST /media/bulk must be defined BEFORE GET /media/{item_id}
to prevent FastAPI matching "bulk" as a path parameter.
"""

from pathlib import Path

from fastapi import APIRouter, Body, Depends, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import Auth
from app.core.exceptions import not_found
from app.core.pagination import PaginatedResponse, PaginationParams
from app.database import get_db
from app.schemas.media_item import (
    BulkActionRequest,
    BulkResult,
    MediaItemDetail,
    MediaItemPatch,
    MediaItemSummary,
)
from app.services import media_service
from app.services.storage_service import get_thumbnail_path

router = APIRouter(prefix="/media", tags=["media"])


@router.get("", response_model=PaginatedResponse[MediaItemSummary])
async def list_media(
    type: str | None = Query(None, description="Filter by media_type: image | video"),
    source_id: str | None = Query(None),
    tag_ids: list[str] = Query(default=[], description="Filter by tag IDs (AND logic)"),
    item_status: str | None = Query(None, alias="status"),
    sort: str = Query(default="date", description="date | name | size | mtime"),
    order: str = Query(default="desc", description="asc | desc"),
    params: PaginationParams = Depends(),
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    return await media_service.list_media(
        db,
        params,
        media_type=type,
        source_id=source_id,
        tag_ids=tag_ids or None,
        status=item_status,
        sort=sort,
        order=order,
    )


@router.post("/bulk", response_model=BulkResult)
async def bulk_action(
    body: BulkActionRequest,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    return await media_service.bulk_action(db, body)


@router.get("/{item_id}", response_model=MediaItemDetail)
async def get_media_item(
    item_id: str,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    return await media_service.get_media_item(db, item_id)


@router.patch("/{item_id}", response_model=MediaItemDetail)
async def patch_media_item(
    item_id: str,
    body: MediaItemPatch,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    return await media_service.patch_media_item(db, item_id, body)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media_item(
    item_id: str,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    await media_service.delete_media_item(db, item_id)


@router.get("/{item_id}/thumbnail", response_class=FileResponse)
async def serve_thumbnail(
    item_id: str,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    """Serve the generated thumbnail JPEG. Returns 404 if not yet generated."""
    item = await media_service.get_media_item_orm(db, item_id)
    path = get_thumbnail_path(item)
    if not path:
        raise not_found("Thumbnail", item_id)
    return FileResponse(str(path), media_type="image/jpeg")


@router.get("/{item_id}/stream")
async def stream_media(
    item_id: str,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    """
    Stream the original media file. Supports HTTP Range requests for video seeking.
    Returns 404 if the file has been removed from disk since indexing.
    """
    item = await media_service.get_media_item_orm(db, item_id)
    file_path = Path(item.file_path)
    if not file_path.exists():
        raise not_found("File", item_id)
    return FileResponse(
        str(file_path),
        media_type=item.mime_type or "application/octet-stream",
    )
