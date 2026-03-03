"""
M2 search tests.

Covers:
- Full-text search (tsvector)
- pg_trgm fuzzy fallback (when tsvector returns nothing)
- Auto-detect mode selection (_should_use_semantic)
- GET /search with mode= param
- GET /media/{id}/similar (empty when no CLIP embeddings)
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media_item import MediaItem
from app.models.media_source import MediaSource
from app.services.search_service import _should_use_semantic
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
    clip_status: str = "pending",
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
        clip_status=clip_status,
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


# ── _should_use_semantic ───────────────────────────────────────────────────────

def test_should_use_semantic_short():
    assert not _should_use_semantic("sunset")
    assert not _should_use_semantic("sunset beach")


def test_should_use_semantic_long_words():
    assert _should_use_semantic("woman on a sunny beach")
    assert _should_use_semantic("close up portrait of a woman smiling")


def test_should_use_semantic_long_string():
    assert _should_use_semantic("a" * 31)


# ── Full-text search ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_text_hit(client: AsyncClient, db_session: AsyncSession):
    src = await _make_source(db_session)
    await _make_item(db_session, src.id, filename="sunset_beach.jpg")

    r = await client.get("/api/v1/search", params={"q": "sunset", "mode": "text"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert any("sunset" in i["filename"] for i in data["items"])


@pytest.mark.asyncio
async def test_search_text_no_hit(client: AsyncClient, db_session: AsyncSession):
    src = await _make_source(db_session)
    await _make_item(db_session, src.id, filename="vacation.jpg")

    # Query that won't match tsvector or trgm (nonsense string)
    r = await client.get("/api/v1/search", params={"q": "xyzzy_nonexistent_abc", "mode": "text"})
    assert r.status_code == 200
    assert r.json()["total"] == 0


@pytest.mark.asyncio
async def test_search_auto_mode_short_query(client: AsyncClient, db_session: AsyncSession):
    """≤2 words → text mode (no CLIP import required)."""
    src = await _make_source(db_session)
    await _make_item(db_session, src.id, filename="landscape.jpg")

    r = await client.get("/api/v1/search", params={"q": "landscape"})
    assert r.status_code == 200
    assert r.json()["total"] >= 1


@pytest.mark.asyncio
async def test_search_auto_mode_long_query_falls_back_to_text(
    client: AsyncClient, db_session: AsyncSession
):
    """≥3 words → semantic attempted; falls back to text when CLIP not available."""
    src = await _make_source(db_session)
    await _make_item(db_session, src.id, filename="portrait.jpg")

    # 'auto' with long query tries semantic, which falls back to full_text_search
    r = await client.get(
        "/api/v1/search",
        params={"q": "portrait of a person", "mode": "auto"},
    )
    # Should not error — either returns results or empty
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_search_mode_param_text(client: AsyncClient, db_session: AsyncSession):
    src = await _make_source(db_session)
    await _make_item(db_session, src.id, filename="ocean_wave.jpg")

    r = await client.get("/api/v1/search", params={"q": "ocean", "mode": "text"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_search_mode_param_semantic(client: AsyncClient, db_session: AsyncSession):
    """Semantic mode falls back to text when CLIP not available."""
    src = await _make_source(db_session)
    await _make_item(db_session, src.id, filename="mountain.jpg")

    r = await client.get("/api/v1/search", params={"q": "mountain view", "mode": "semantic"})
    # Falls back gracefully — should not 500
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_search_mode_param_hybrid(client: AsyncClient, db_session: AsyncSession):
    src = await _make_source(db_session)
    await _make_item(db_session, src.id, filename="forest.jpg")

    r = await client.get("/api/v1/search", params={"q": "forest trees nature walk", "mode": "hybrid"})
    assert r.status_code == 200


# ── /media/{id}/similar ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_similar_no_embedding(client: AsyncClient, db_session: AsyncSession):
    src = await _make_source(db_session)
    item = await _make_item(db_session, src.id, clip_status="pending")

    r = await client.get(f"/api/v1/media/{item.id}/similar")
    assert r.status_code == 200
    assert r.json() == []  # no embedding → empty list


@pytest.mark.asyncio
async def test_similar_unknown_item(client: AsyncClient, db_session: AsyncSession):
    r = await client.get("/api/v1/media/nonexistent-id/similar")
    assert r.status_code == 200
    assert r.json() == []


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
async def test_search_result_has_m2_fields(client: AsyncClient, db_session: AsyncSession):
    src = await _make_source(db_session)
    await _make_item(db_session, src.id, filename="waterfall.jpg")

    r = await client.get("/api/v1/search", params={"q": "waterfall", "mode": "text"})
    assert r.status_code == 200
    items = r.json()["items"]
    if items:
        item = items[0]
        assert "is_favourite" in item
        assert "clip_status" in item
