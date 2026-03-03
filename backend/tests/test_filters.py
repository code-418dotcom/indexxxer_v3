"""
Saved filter CRUD tests.

GET    /filters
POST   /filters
GET    /filters/{id}
PUT    /filters/{id}
DELETE /filters/{id}
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# ── Helpers ────────────────────────────────────────────────────────────────────

SAMPLE_FILTERS = {
    "type": "image",
    "sort": "date",
    "order": "desc",
}


# ── List ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_filters_empty(client: AsyncClient, db_session: AsyncSession):
    r = await client.get("/api/v1/filters")
    assert r.status_code == 200
    assert r.json() == []


# ── Create ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_filter(client: AsyncClient, db_session: AsyncSession):
    payload = {"name": "Images only", "filters": SAMPLE_FILTERS}
    r = await client.post("/api/v1/filters", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Images only"
    assert data["filters"]["type"] == "image"
    assert data["is_default"] is False
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_filter_with_default(client: AsyncClient, db_session: AsyncSession):
    payload = {"name": "Default view", "filters": {}, "is_default": True}
    r = await client.post("/api/v1/filters", json=payload)
    assert r.status_code == 201
    assert r.json()["is_default"] is True


# ── Get ────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_filter(client: AsyncClient, db_session: AsyncSession):
    r = await client.post(
        "/api/v1/filters", json={"name": "Videos", "filters": {"type": "video"}}
    )
    filter_id = r.json()["id"]

    r2 = await client.get(f"/api/v1/filters/{filter_id}")
    assert r2.status_code == 200
    assert r2.json()["name"] == "Videos"


@pytest.mark.asyncio
async def test_get_filter_not_found(client: AsyncClient, db_session: AsyncSession):
    r = await client.get("/api/v1/filters/nonexistent-id")
    assert r.status_code == 404


# ── Update ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_filter_name(client: AsyncClient, db_session: AsyncSession):
    r = await client.post(
        "/api/v1/filters", json={"name": "Old name", "filters": SAMPLE_FILTERS}
    )
    filter_id = r.json()["id"]

    r2 = await client.put(f"/api/v1/filters/{filter_id}", json={"name": "New name"})
    assert r2.status_code == 200
    assert r2.json()["name"] == "New name"
    # filters unchanged
    assert r2.json()["filters"]["type"] == "image"


@pytest.mark.asyncio
async def test_update_filter_payload(client: AsyncClient, db_session: AsyncSession):
    r = await client.post(
        "/api/v1/filters", json={"name": "Test", "filters": {"type": "image"}}
    )
    filter_id = r.json()["id"]

    new_filters = {"type": "video", "sort": "name"}
    r2 = await client.put(f"/api/v1/filters/{filter_id}", json={"filters": new_filters})
    assert r2.status_code == 200
    assert r2.json()["filters"]["type"] == "video"


@pytest.mark.asyncio
async def test_update_filter_not_found(client: AsyncClient, db_session: AsyncSession):
    r = await client.put("/api/v1/filters/no-such-id", json={"name": "x"})
    assert r.status_code == 404


# ── Delete ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_filter(client: AsyncClient, db_session: AsyncSession):
    r = await client.post(
        "/api/v1/filters", json={"name": "To delete", "filters": {}}
    )
    filter_id = r.json()["id"]

    r2 = await client.delete(f"/api/v1/filters/{filter_id}")
    assert r2.status_code == 204

    r3 = await client.get(f"/api/v1/filters/{filter_id}")
    assert r3.status_code == 404


@pytest.mark.asyncio
async def test_delete_filter_not_found(client: AsyncClient, db_session: AsyncSession):
    r = await client.delete("/api/v1/filters/nonexistent")
    assert r.status_code == 404


# ── Round-trip ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_filter_round_trip(client: AsyncClient, db_session: AsyncSession):
    """Create → list → get → update → delete."""
    # Create
    r = await client.post(
        "/api/v1/filters",
        json={"name": "Round trip", "filters": {"type": "image", "sort": "relevance"}},
    )
    assert r.status_code == 201
    fid = r.json()["id"]

    # List
    r2 = await client.get("/api/v1/filters")
    assert any(f["id"] == fid for f in r2.json())

    # Get
    r3 = await client.get(f"/api/v1/filters/{fid}")
    assert r3.json()["name"] == "Round trip"

    # Update
    r4 = await client.put(f"/api/v1/filters/{fid}", json={"name": "Updated"})
    assert r4.json()["name"] == "Updated"

    # Delete
    r5 = await client.delete(f"/api/v1/filters/{fid}")
    assert r5.status_code == 204

    # Confirm gone
    r6 = await client.get(f"/api/v1/filters/{fid}")
    assert r6.status_code == 404
