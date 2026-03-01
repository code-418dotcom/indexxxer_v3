"""
Media source CRUD + scan trigger endpoints.
"""

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import Auth
from app.database import get_db
from app.schemas.index_job import JobResponse, ScanRequest
from app.schemas.media_source import SourceCreate, SourceResponse, SourceUpdate
from app.services import source_service

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceResponse])
async def list_sources(
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    return await source_service.list_sources(db)


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    body: SourceCreate,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    return await source_service.create_source(db, body)


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: str,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    return await source_service.get_source(db, source_id)


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: str,
    body: SourceUpdate,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    return await source_service.update_source(db, source_id, body)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: str,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    await source_service.delete_source(db, source_id)


@router.post(
    "/{source_id}/scan",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_scan(
    source_id: str,
    body: ScanRequest | None = Body(default=None),
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    """
    Enqueue a scan job for a media source.
    Body is optional; omitting it uses job_type='full'.
    """
    req = body or ScanRequest()
    return await source_service.trigger_scan(db, source_id, req)
