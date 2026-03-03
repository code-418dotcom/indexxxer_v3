"""
FastAPI dependency injection helpers.

M4: get_current_user returns a User object.
    Falls back to static API token (backward compat) → returns first admin user.
    require_admin checks role == "admin".
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.redis_pool import get_redis
from app.core.security import decode_token
from app.database import get_db
from app.models.user import User
from app.services import user_service

# Accept token via either header style:
#   Authorization: Bearer <token>
#   X-API-Token: <token>
_bearer_scheme = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-Token", auto_error=False)


async def get_current_user(
    bearer: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer_scheme)],
    api_key: Annotated[str | None, Security(_api_key_header)],
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Resolve the authenticated user from:
      1. Authorization: Bearer <JWT>
      2. X-API-Token: <JWT-or-static>
    Falls back to static api_token for backward compatibility.
    """
    raw_token = (bearer.credentials if bearer else None) or api_key
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Try JWT first ──────────────────────────────────────────────────────────
    try:
        payload = decode_token(raw_token)
        if payload.get("type") != "access":
            raise JWTError("not an access token")

        # Check blacklist (swallow Redis errors so tests without Redis still work)
        jti = payload.get("jti")
        if jti:
            try:
                redis = get_redis()
                blacklisted = await redis.exists(f"blacklist:{jti}")
                if blacklisted:
                    raise JWTError("token revoked")
            except JWTError:
                raise
            except Exception:
                pass  # Redis unavailable — skip blacklist check

        user_id = payload.get("sub")
        user = await user_service.get_by_id(db, user_id)
        if not user or not user.enabled:
            raise JWTError("user not found or disabled")
        return user

    except JWTError:
        pass  # fall through to static-token check

    # ── Static API token fallback (backward compat) ────────────────────────────
    if raw_token == settings.api_token:
        from sqlalchemy import select
        result = await db.execute(
            select(User).where(User.role == "admin", User.enabled.is_(True)).limit(1)
        )
        admin = result.scalar_one_or_none()
        if admin:
            return admin
        # No admin exists yet (e.g. during tests before seed) — create a dummy
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No admin user configured; run seed_admin first",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user


# Convenience alias — use as `_: None = Auth` or `current_user: User = Auth` in routers
Auth = Depends(get_current_user)
