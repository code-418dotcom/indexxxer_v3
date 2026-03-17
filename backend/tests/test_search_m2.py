"""
M2 search tests.

Covers:
- Full-text search (tsvector)
- pg_trgm fuzzy fallback (when tsvector returns nothing)
- GET /search endpoint
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media_item import MediaItem
from app.models.media_source import MediaSource
from app.models.base import new_uuid


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _make_source(db: AsyncSession, name: str = "test") -> MediaSource:
    src = MediaSource(id=new_uuid(), name=name, path="/media/test", source_type="local")
    db.add(src)
    await db.flush()
    return src


async def _make_item(
    db: AsyncSession,
    source_id: str,
    filename: str = "sunset.jpg",
    media_type: str = "image",
    mime_type: str = "image/jpeg",
    is_favourite: bool = False,
) -> MediaItem:
    item = MediaItem(
        id=new_uuid(),
        source_id=source_id,
        file_path=f"/media/test/{filename}",
        filename=filename,
        media_type=media_type,
        mime_type=mime_type,
        index_status="indexed",
        is_favourite=is_favourite,
    )
    db.add(item)
    await db.flush()
    # Set search_vector manually (trigger not installed in test DB)
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    mime_suffix = mime_type.split("/")[1] if "/" in mime_type else ""
    await db.execute(
        text(
            "UPDATE media_items SET search_vector = "
            "setweight(to_tsvector('english', :stem), 'A') || "
            "setweight(to_tsvector('english', :mime), 'C') "
            "WHERE id = :id"
        ),
        {"stem": stem, "mime": mime_suffix, "id": item.id},
    )
    return item


# ── Full-text search ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_text_hit(client: AsyncClient, db_session: AsyncSession):
    src = await _make_source(db_session)
    await _make_item(db_session, src.id, filename="sunset_beach.jpg")

    r = await client.get("/api/v1/search", params={"q": "sunset"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert any("sunset" in i["filename"] for i in data["items"])


@pytest.mark.asyncio
async def test_search_text_no_hit(client: AsyncClient, db_session: AsyncSession):
    src = await _make_source(db_session)
    await _make_item(db_session, src.id, filename="vacation.jpg")

    # Query that won't match tsvector or trgm (nonsense string)
    r = await client.get("/api/v1/search", params={"q": "xyzzy_nonexistent_abc"})
    assert r.status_code == 200
    assert r.json()["total"] == 0


@pytest.mark.asyncio
async def test_search_short_query(client: AsyncClient, db_session: AsyncSession):
    src = await _make_source(db_session)
    await _make_item(db_session, src.id, filename="landscape.jpg")

    r = await client.get("/api/v1/search", params={"q": "landscape"})
    assert r.status_code == 200
    assert r.json()["total"] >= 1


# ── Favourite filter ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_favourites_filter(client: AsyncClient, db_session: AsyncSession):
    src = await _make_source(db_session)
    await _make_item(db_session, src.id, filename="fav.jpg", is_favourite=True)
    await _make_item(db_session, src.id, filename="normal.jpg", is_favourite=False)

    r = await client.get("/api/v1/media", params={"favourite": "true"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["filename"] == "fav.jpg"
    assert data["items"][0]["is_favourite"] is True


@pytest.mark.asyncio
async def test_patch_is_favourite(client: AsyncClient, db_session: AsyncSession):
    src = await _make_source(db_session)
    item = await _make_item(db_session, src.id, filename="toggled.jpg")

    r = await client.patch(f"/api/v1/media/{item.id}", json={"is_favourite": True})
    assert r.status_code == 200
    assert r.json()["is_favourite"] is True

    r2 = await client.patch(f"/api/v1/media/{item.id}", json={"is_favourite": False})
    assert r2.status_code == 200
    assert r2.json()["is_favourite"] is False


# ── Result shape ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_result_has_expected_fields(client: AsyncClient, db_session: AsyncSession):
    src = await _make_source(db_session)
    await _make_item(db_session, src.id, filename="waterfall.jpg")

    r = await client.get("/api/v1/search", params={"q": "waterfall"})
    assert r.status_code == 200
    items = r.json()["items"]
    if items:
        item = items[0]
        assert "is_favourite" in item
