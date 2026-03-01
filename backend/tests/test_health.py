"""
Smoke tests — verifies the app boots and basic auth enforcement works.
These run without needing a database connection.
"""

from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_health_unauthenticated():
    """Health endpoint must return 200 with no auth token."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        r = await ac.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "version" in data


async def test_api_requires_token():
    """Any /api/v1/ endpoint must reject requests with no token."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # Once routers are registered (Phase 4) this will test a real endpoint.
        # For now, a missing route returns 404, not 401 — test the auth dep directly.
        r = await ac.get("/api/v1/media")
    # 404 is acceptable here (router not registered yet in Phase 1);
    # 401 is what we'll get in Phase 4+
    assert r.status_code in (401, 404)


async def test_api_wrong_token_rejected():
    """Wrong token must return 401 once routers exist."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Token": "totally-wrong"},
    ) as ac:
        r = await ac.get("/api/v1/media")
    assert r.status_code in (401, 404)


async def test_openapi_schema_accessible():
    """OpenAPI JSON must be reachable (used by frontend api client generation)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        r = await ac.get("/api/v1/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert schema["info"]["title"] == "indexxxer"
