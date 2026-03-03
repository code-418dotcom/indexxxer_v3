"""
User account CRUD + authentication.
"""

from __future__ import annotations

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate

log = structlog.get_logger(__name__)


async def create_user(db: AsyncSession, data: UserCreate) -> UserResponse:
    existing = await get_by_email(db, data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    existing_uname = await db.execute(select(User).where(User.username == data.username))
    if existing_uname.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )
    user = User(
        email=data.email,
        username=data.username,
        password_hash=hash_password(data.password),
        role=data.role,
        enabled=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, user_id: str) -> User | None:
    return await db.get(User, user_id)


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_by_email(db, email)
    if not user:
        return None
    if not user.password_hash or not verify_password(password, user.password_hash):
        return None
    if not user.enabled:
        return None
    return user


async def list_users(
    db: AsyncSession, offset: int = 0, limit: int = 50
) -> tuple[list[UserResponse], int]:
    total_result = await db.execute(select(func.count()).select_from(User))
    total = total_result.scalar_one()
    result = await db.execute(select(User).offset(offset).limit(limit))
    users = [UserResponse.model_validate(u) for u in result.scalars()]
    return users, total


async def update_user(db: AsyncSession, user_id: str, data: UserUpdate) -> UserResponse:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if data.email is not None:
        user.email = data.email
    if data.username is not None:
        user.username = data.username
    if data.password is not None:
        user.password_hash = hash_password(data.password)
    if data.role is not None:
        user.role = data.role
    if data.enabled is not None:
        user.enabled = data.enabled
    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)


async def delete_user(db: AsyncSession, user_id: str) -> None:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await db.delete(user)


async def seed_admin(db: AsyncSession) -> None:
    """Create the first admin account if no users exist yet."""
    result = await db.execute(select(func.count()).select_from(User))
    count = result.scalar_one()
    if count == 0:
        user = User(
            email=settings.admin_email,
            username="admin",
            password_hash=hash_password(settings.admin_password),
            role="admin",
            enabled=True,
        )
        db.add(user)
        await db.flush()
        log.info("admin.seeded", email=settings.admin_email)
