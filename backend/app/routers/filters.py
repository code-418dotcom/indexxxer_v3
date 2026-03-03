"""
Saved filter CRUD endpoints.

GET    /filters          — list all saved filters
POST   /filters          — create a saved filter
GET    /filters/{id}     — get a single filter
PUT    /filters/{id}     — update a filter
DELETE /filters/{id}     — delete a filter
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import Auth
from app.database import get_db
from app.schemas.saved_filter import FilterCreate, FilterResponse, FilterUpdate
from app.services import filter_service

router = APIRouter(prefix="/filters", tags=["filters"])


@router.get("", response_model=list[FilterResponse])
async def list_filters(
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    return await filter_service.list_filters(db)


@router.post("", response_model=FilterResponse, status_code=status.HTTP_201_CREATED)
async def create_filter(
    body: FilterCreate,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    return await filter_service.create_filter(db, body)


@router.get("/{filter_id}", response_model=FilterResponse)
async def get_filter(
    filter_id: str,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    return await filter_service.get_filter(db, filter_id)


@router.put("/{filter_id}", response_model=FilterResponse)
async def update_filter(
    filter_id: str,
    body: FilterUpdate,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    return await filter_service.update_filter(db, filter_id, body)


@router.delete("/{filter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_filter(
    filter_id: str,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    await filter_service.delete_filter(db, filter_id)
