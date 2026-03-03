"""
Tests for M4 JWT auth endpoints.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import create_access_token
from app.services import user_service
from app.schemas.user import UserCreate


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, db_session: AsyncSession):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": settings.admin_email, "password": settings.admin_password},
        headers={},  # No auth header for login
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": settings.admin_email, "password": "wrong-password"},
        headers={},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_disabled_user(client: AsyncClient, db_session: AsyncSession):
    # Create a disabled user
    await user_service.create_user(
        db_session,
        UserCreate(email="disabled@test.local", username="disabled", password="pass123"),
    )
    # Disable them
    from sqlalchemy import select
    from app.models.user import User
    result = await db_session.execute(select(User).where(User.email == "disabled@test.local"))
    u = result.scalar_one()
    u.enabled = False
    await db_session.flush()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "disabled@test.local", "password": "pass123"},
        headers={},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_user_info(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == settings.admin_email
    assert data["role"] == "admin"
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, db_session: AsyncSession):
    # Get a real token pair first
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": settings.admin_email, "password": settings.admin_password},
        headers={},
    )
    assert resp.status_code == 200
    refresh_token = resp.json()["refresh_token"]

    # Refresh
    resp2 = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
        headers={},
    )
    assert resp2.status_code == 200
    data = resp2.json()
    assert "access_token" in data
    assert data["refresh_token"] != refresh_token  # rotated


@pytest.mark.asyncio
async def test_static_token_backward_compat(db_session, fastapi_app):
    """Old X-API-Token header (no JWT) should still work as long as admin user exists."""
    from httpx import ASGITransport
    from app.database import get_db

    async def _override():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=fastapi_app),
            base_url="http://test",
            headers={"X-API-Token": "test-token-insecure"},  # NO JWT header
        ) as raw_client:
            resp = await raw_client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"
    finally:
        fastapi_app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_admin_only_endpoint_requires_admin(client: AsyncClient, db_session: AsyncSession):
    # Create a regular user
    user = await user_service.create_user(
        db_session,
        UserCreate(email="regular@test.local", username="regular", password="pass123", role="user"),
    )
    user_token = create_access_token(user.id, "user")

    resp = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 403
