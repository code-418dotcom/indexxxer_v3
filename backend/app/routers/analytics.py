"""
Analytics endpoints (admin only).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.database import get_db
from app.models.user import User
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])

_admin = Depends(require_admin)


@router.get("/overview")
async def get_overview(_: User = _admin, db: AsyncSession = Depends(get_db)):
    return await analytics_service.get_overview(db)


@router.get("/queries")
async def get_search_stats(
    days: int = 30,
    _: User = _admin,
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_search_stats(db, days)


@router.get("/indexing")
async def get_indexing_stats(
    days: int = 30,
    _: User = _admin,
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_indexing_stats(db, days)
