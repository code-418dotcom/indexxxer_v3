"""
Tests for M4 analytics endpoints + query logging.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch


@pytest.mark.asyncio
async def test_analytics_overview(client: AsyncClient, db_session: AsyncSession):
    resp = await client.get("/api/v1/analytics/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_media" in data
    assert "storage_bytes" in data
    assert "source_count" in data


@pytest.mark.asyncio
async def test_analytics_search_stats(client: AsyncClient, db_session: AsyncSession):
    # Seed some query logs
    from app.models.query_log import QueryLog

    for i in range(3):
        db_session.add(QueryLog(query=f"test query {i}", search_mode="text", result_count=5, latency_ms=50))
    await db_session.flush()

    resp = await client.get("/api/v1/analytics/queries?days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_searches" in data
    assert "daily" in data
    assert "top_queries" in data


@pytest.mark.asyncio
async def test_analytics_indexing_stats(client: AsyncClient, db_session: AsyncSession):
    resp = await client.get("/api/v1/analytics/indexing?days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert "daily_indexed" in data
    assert "error_count" in data


@pytest.mark.asyncio
async def test_query_logged_on_search(client: AsyncClient, db_session: AsyncSession):
    """Search endpoint should dispatch a log_query_task."""
    with patch("app.workers.tasks.analytics.log_query_task.apply_async") as mock_apply:
        resp = await client.get("/api/v1/search?q=testquery&mode=text")
        # Search may return 200 or fail due to no CLIP model — either way the task should be called
        mock_apply.assert_called_once()
        kwargs = mock_apply.call_args[1]["kwargs"]
        assert kwargs["query"] == "testquery"
        assert kwargs["search_mode"] in ("text", "auto")


@pytest.mark.asyncio
async def test_analytics_requires_admin(client: AsyncClient, db_session: AsyncSession):
    """Regular users should get 403 on analytics endpoints."""
    from app.core.security import create_access_token
    from app.services import user_service
    from app.schemas.user import UserCreate

    user = await user_service.create_user(
        db_session,
        UserCreate(email="user2@test.local", username="user2", password="pass123", role="user"),
    )
    user_token = create_access_token(user.id, "user")

    resp = await client.get(
        "/api/v1/analytics/overview",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 403
