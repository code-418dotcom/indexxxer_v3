"""CRUD service for SavedFilter."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import not_found
from app.models.saved_filter import SavedFilter
from app.models.base import new_uuid
from app.schemas.saved_filter import FilterCreate, FilterResponse, FilterUpdate


async def list_filters(db: AsyncSession) -> list[FilterResponse]:
    rows = (
        await db.execute(select(SavedFilter).order_by(SavedFilter.name))
    ).scalars().all()
    return [FilterResponse.model_validate(r) for r in rows]


async def create_filter(db: AsyncSession, body: FilterCreate) -> FilterResponse:
    obj = SavedFilter(
        id=new_uuid(),
        name=body.name,
        filters=body.filters,
        is_default=body.is_default,
    )
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    return FilterResponse.model_validate(obj)


async def get_filter(db: AsyncSession, filter_id: str) -> FilterResponse:
    obj = await db.get(SavedFilter, filter_id)
    if not obj:
        raise not_found("SavedFilter", filter_id)
    return FilterResponse.model_validate(obj)


async def update_filter(
    db: AsyncSession, filter_id: str, body: FilterUpdate
) -> FilterResponse:
    obj = await db.get(SavedFilter, filter_id)
    if not obj:
        raise not_found("SavedFilter", filter_id)
    if body.name is not None:
        obj.name = body.name
    if body.filters is not None:
        obj.filters = body.filters
    if body.is_default is not None:
        obj.is_default = body.is_default
    await db.flush()
    await db.refresh(obj)
    return FilterResponse.model_validate(obj)


async def delete_filter(db: AsyncSession, filter_id: str) -> None:
    obj = await db.get(SavedFilter, filter_id)
    if not obj:
        raise not_found("SavedFilter", filter_id)
    await db.delete(obj)
    await db.flush()
