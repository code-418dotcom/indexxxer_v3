"""
Tests for GET/POST/PUT/DELETE /tags and GET /tags/{id}/media endpoints.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media_item import MediaItem
from app.models.media_source import MediaSource
from app.models.tag import MediaTag, Tag


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def source(db_session: AsyncSession) -> MediaSource:
    s = MediaSource(name="Tags Source", path="/media/tags", source_type="local")
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.fixture
async def tag(db_session: AsyncSession) -> Tag:
    t = Tag(name="Nature", slug="nature", category="genre", color="#22c55e")
    db_session.add(t)
    await db_session.flush()
    return t


@pytest.fixture
async def tagged_item(db_session: AsyncSession, source: MediaSource, tag: Tag) -> MediaItem:
    item = MediaItem(
        source_id=source.id,
        file_path="/media/tags/forest.jpg",
        filename="forest.jpg",
        media_type="image",
        mime_type="image/jpeg",
        file_size=512_000,
        index_status="indexed",
    )
    db_session.add(item)
    await db_session.flush()
    mt = MediaTag(media_id=item.id, tag_id=tag.id, confidence=1.0, source="manual")
    db_session.add(mt)
    await db_session.flush()
    return item


# ── List tags ──────────────────────────────────────────────────────────────────


async def test_list_tags_empty(client):
    resp = await client.get("/api/v1/tags")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_list_tags_returns_tags(client, tag):
    resp = await client.get("/api/v1/tags")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Nature"
    assert data["items"][0]["slug"] == "nature"


async def test_list_tags_filter_by_category(client, tag):
    resp = await client.get("/api/v1/tags?category=genre")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    resp2 = await client.get("/api/v1/tags?category=studio")
    assert resp2.status_code == 200
    assert resp2.json()["total"] == 0


async def test_list_tags_search_by_name(client, tag):
    resp = await client.get("/api/v1/tags?q=natur")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    resp2 = await client.get("/api/v1/tags?q=xyz")
    assert resp2.status_code == 200
    assert resp2.json()["total"] == 0


async def test_list_tags_requires_auth(client):
    resp = await client.get("/api/v1/tags", headers={"X-API-Token": "bad"})
    assert resp.status_code == 401


# ── Create tag ────────────────────────────────────────────────────────────────


async def test_create_tag_minimal(client):
    resp = await client.post("/api/v1/tags", json={"name": "Portrait"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Portrait"
    assert data["slug"] == "portrait"
    assert data["id"]


async def test_create_tag_with_all_fields(client):
    resp = await client.post(
        "/api/v1/tags",
        json={"name": "Studio X", "category": "studio", "color": "#3b82f6"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["category"] == "studio"
    assert data["color"] == "#3b82f6"


async def test_create_tag_missing_name(client):
    resp = await client.post("/api/v1/tags", json={"category": "genre"})
    assert resp.status_code == 422


# ── Get tag ───────────────────────────────────────────────────────────────────


async def test_get_tag(client, tag):
    resp = await client.get(f"/api/v1/tags/{tag.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == tag.id
    assert data["name"] == "Nature"


async def test_get_tag_not_found(client):
    resp = await client.get("/api/v1/tags/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ── Update tag ────────────────────────────────────────────────────────────────


async def test_update_tag(client, tag):
    resp = await client.put(
        f"/api/v1/tags/{tag.id}",
        json={"name": "Landscape", "color": "#f59e0b"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Landscape"
    assert data["color"] == "#f59e0b"


async def test_update_tag_not_found(client):
    resp = await client.put(
        "/api/v1/tags/00000000-0000-0000-0000-000000000000",
        json={"name": "X"},
    )
    assert resp.status_code == 404


# ── Delete tag ────────────────────────────────────────────────────────────────


async def test_delete_tag(client, tag):
    resp = await client.delete(f"/api/v1/tags/{tag.id}")
    assert resp.status_code == 204
    resp2 = await client.get(f"/api/v1/tags/{tag.id}")
    assert resp2.status_code == 404


async def test_delete_tag_not_found(client):
    resp = await client.delete("/api/v1/tags/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ── Tag media ─────────────────────────────────────────────────────────────────


async def test_get_tag_media(client, tag, tagged_item):
    resp = await client.get(f"/api/v1/tags/{tag.id}/media")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == tagged_item.id


async def test_get_tag_media_empty(client, tag):
    resp = await client.get(f"/api/v1/tags/{tag.id}/media")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
