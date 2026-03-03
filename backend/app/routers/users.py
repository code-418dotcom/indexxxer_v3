"""
User management endpoints (admin only).
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])

_admin = Depends(require_admin)


@router.get("", response_model=list[UserResponse])
async def list_users(
    offset: int = 0,
    limit: int = 50,
    _: User = _admin,
    db: AsyncSession = Depends(get_db),
):
    users, _ = await user_service.list_users(db, offset, limit)
    return users


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    _: User = _admin,
    db: AsyncSession = Depends(get_db),
):
    return await user_service.create_user(db, body)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    _: User = _admin,
    db: AsyncSession = Depends(get_db),
):
    from fastapi import HTTPException
    user = await user_service.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    body: UserUpdate,
    _: User = _admin,
    db: AsyncSession = Depends(get_db),
):
    return await user_service.update_user(db, user_id, body)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    _: User = _admin,
    db: AsyncSession = Depends(get_db),
):
    await user_service.delete_user(db, user_id)
