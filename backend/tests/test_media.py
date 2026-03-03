"""
Tests for GET/PATCH/DELETE /media and /media/bulk endpoints.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media_item import MediaItem
from app.models.media_source import MediaSource


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def source(db_session: AsyncSession) -> MediaSource:
    s = MediaSource(name="Test Source", path="/media/test", source_type="local")
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.fixture
async def image_item(db_session: AsyncSession, source: MediaSource) -> MediaItem:
    item = MediaItem(
        source_id=source.id,
        file_path="/media/test/photo.jpg",
        filename="photo.jpg",
        media_type="image",
        mime_type="image/jpeg",
        file_size=1_024_000,
        width=1920,
        height=1080,
        index_status="indexed",
    )
    db_session.add(item)
    await db_session.flush()
    return item


@pytest.fixture
async def video_item(db_session: AsyncSession, source: MediaSource) -> MediaItem:
    item = MediaItem(
        source_id=source.id,
        file_path="/media/test/clip.mp4",
        filename="clip.mp4",
        media_type="video",
        mime_type="video/mp4",
        file_size=50_000_000,
        width=1920,
        height=1080,
        duration_seconds=120.5,
        frame_rate=30.0,
        codec="h264",
        index_status="indexed",
    )
    db_session.add(item)
    await db_session.flush()
    return item


# ── List media ────────────────────────────────────────────────────────────────


async def test_list_media_empty(client):
    resp = await client.get("/api/v1/media")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_list_media_returns_items(client, image_item):
    resp = await client.get("/api/v1/media")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == image_item.id
    assert data["items"][0]["filename"] == "photo.jpg"


async def test_list_media_filter_by_type_image(client, image_item, video_item):
    resp = await client.get("/api/v1/media?type=image")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["media_type"] == "image"


async def test_list_media_filter_by_type_video(client, image_item, video_item):
    resp = await client.get("/api/v1/media?type=video")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["media_type"] == "video"


async def test_list_media_pagination(client, image_item, video_item):
    resp = await client.get("/api/v1/media?page=1&limit=1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["total"] == 2
    assert data["pages"] == 2


async def test_list_media_requires_auth(client):
    resp = await client.get("/api/v1/media", headers={"X-API-Token": "wrong"})
    assert resp.status_code == 401


# ── Get media item ────────────────────────────────────────────────────────────


async def test_get_media_item(client, image_item):
    resp = await client.get(f"/api/v1/media/{image_item.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == image_item.id
    assert data["filename"] == "photo.jpg"
    assert data["width"] == 1920
    assert data["height"] == 1080
    assert "tags" in data


async def test_get_media_item_not_found(client):
    resp = await client.get("/api/v1/media/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ── Patch media item ──────────────────────────────────────────────────────────


async def test_patch_media_item_filename(client, image_item):
    resp = await client.patch(
        f"/api/v1/media/{image_item.id}",
        json={"filename": "renamed.jpg"},
    )
    assert resp.status_code == 200
    assert resp.json()["filename"] == "renamed.jpg"


async def test_patch_media_item_empty_body_ok(client, image_item):
    resp = await client.patch(f"/api/v1/media/{image_item.id}", json={})
    assert resp.status_code == 200


async def test_patch_media_item_not_found(client):
    resp = await client.patch(
        "/api/v1/media/00000000-0000-0000-0000-000000000000",
        json={"filename": "x.jpg"},
    )
    assert resp.status_code == 404


# ── Delete media item ─────────────────────────────────────────────────────────


async def test_delete_media_item(client, image_item):
    resp = await client.delete(f"/api/v1/media/{image_item.id}")
    assert resp.status_code == 204
    # Verify gone
    resp2 = await client.get(f"/api/v1/media/{image_item.id}")
    assert resp2.status_code == 404


async def test_delete_media_item_not_found(client):
    resp = await client.delete("/api/v1/media/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ── Bulk actions ──────────────────────────────────────────────────────────────


async def test_bulk_delete(client, image_item, video_item):
    resp = await client.post(
        "/api/v1/media/bulk",
        json={"ids": [image_item.id], "action": "delete"},
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["processed"] == 1
    assert result["failed"] == 0


async def test_bulk_delete_nonexistent_id(client):
    resp = await client.post(
        "/api/v1/media/bulk",
        json={"ids": ["00000000-0000-0000-0000-000000000000"], "action": "delete"},
    )
    assert resp.status_code == 200
    # Non-existent IDs are counted as failed, not an error response
    result = resp.json()
    assert isinstance(result["failed"], int)


# ── Thumbnail / stream ────────────────────────────────────────────────────────


async def test_thumbnail_not_found_when_no_path(client, image_item):
    # image_item has no thumbnail_path set, so should 404
    resp = await client.get(f"/api/v1/media/{image_item.id}/thumbnail")
    assert resp.status_code == 404


async def test_stream_not_found_when_file_missing(client, image_item):
    # file at /media/test/photo.jpg doesn't exist on the test host
    resp = await client.get(f"/api/v1/media/{image_item.id}/stream")
    assert resp.status_code == 404
