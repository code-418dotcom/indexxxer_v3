"""
Tests for GET/POST/PUT/DELETE /sources and POST /sources/{id}/scan endpoints.
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media_source import MediaSource


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def source(db_session: AsyncSession) -> MediaSource:
    s = MediaSource(name="My Library", path="/media/lib", source_type="local", enabled=True)
    db_session.add(s)
    await db_session.flush()
    return s


# ── List sources ──────────────────────────────────────────────────────────────


async def test_list_sources_empty(client):
    resp = await client.get("/api/v1/sources")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_sources_returns_sources(client, source):
    resp = await client.get("/api/v1/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "My Library"
    assert data[0]["path"] == "/media/lib"


async def test_list_sources_requires_auth(client):
    resp = await client.get("/api/v1/sources", headers={"X-API-Token": "wrong"})
    assert resp.status_code == 401


# ── Create source ─────────────────────────────────────────────────────────────


async def test_create_source_minimal(client):
    resp = await client.post(
        "/api/v1/sources",
        json={"name": "Archive", "path": "/media/archive"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Archive"
    assert data["path"] == "/media/archive"
    assert data["source_type"] == "local"
    assert data["enabled"] is True
    assert data["id"]


async def test_create_source_with_type(client):
    resp = await client.post(
        "/api/v1/sources",
        json={"name": "SMB Share", "path": "//nas/share", "source_type": "local"},
    )
    assert resp.status_code == 201
    assert resp.json()["source_type"] == "local"


async def test_create_source_missing_fields(client):
    resp = await client.post("/api/v1/sources", json={"name": "No path"})
    assert resp.status_code == 422


# ── Get source ────────────────────────────────────────────────────────────────


async def test_get_source(client, source):
    resp = await client.get(f"/api/v1/sources/{source.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == source.id
    assert data["name"] == "My Library"


async def test_get_source_not_found(client):
    resp = await client.get("/api/v1/sources/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ── Update source ─────────────────────────────────────────────────────────────


async def test_update_source_name(client, source):
    resp = await client.put(
        f"/api/v1/sources/{source.id}",
        json={"name": "Renamed Library"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed Library"


async def test_update_source_disable(client, source):
    resp = await client.put(f"/api/v1/sources/{source.id}", json={"enabled": False})
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


async def test_update_source_not_found(client):
    resp = await client.put(
        "/api/v1/sources/00000000-0000-0000-0000-000000000000",
        json={"name": "X"},
    )
    assert resp.status_code == 404


# ── Delete source ─────────────────────────────────────────────────────────────


async def test_delete_source(client, source):
    resp = await client.delete(f"/api/v1/sources/{source.id}")
    assert resp.status_code == 204
    resp2 = await client.get(f"/api/v1/sources/{source.id}")
    assert resp2.status_code == 404


async def test_delete_source_not_found(client):
    resp = await client.delete("/api/v1/sources/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ── Trigger scan ──────────────────────────────────────────────────────────────


async def test_trigger_scan(client, source):
    # Mock the Celery task dispatch so we don't need a running broker in tests
    mock_result = MagicMock()
    mock_result.id = "celery-task-id-123"

    with patch(
        "app.workers.tasks.scan.scan_source_task.apply_async",
        return_value=mock_result,
    ):
        resp = await client.post(
            f"/api/v1/sources/{source.id}/scan",
            json={"job_type": "full"},
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["source_id"] == source.id
    assert data["job_type"] == "full"
    assert data["status"] == "pending"
    assert data["id"]


async def test_trigger_scan_incremental(client, source):
    mock_result = MagicMock()
    mock_result.id = "celery-task-id-456"

    with patch(
        "app.workers.tasks.scan.scan_source_task.apply_async",
        return_value=mock_result,
    ):
        resp = await client.post(
            f"/api/v1/sources/{source.id}/scan",
            json={"job_type": "incremental"},
        )

    assert resp.status_code == 202
    assert resp.json()["job_type"] == "incremental"


async def test_trigger_scan_source_not_found(client):
    resp = await client.post(
        "/api/v1/sources/00000000-0000-0000-0000-000000000000/scan",
        json={"job_type": "full"},
    )
    assert resp.status_code == 404
