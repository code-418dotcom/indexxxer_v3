"""
Tests for GET /search and GET /search/suggestions endpoints.

Note on FTS in tests:
    The tsvector trigger (trg_media_search_vector) is defined in the Alembic
    migration, NOT in the ORM metadata, so it is NOT present when
    Base.metadata.create_all() creates tables in the test DB.
    Tests that exercise FTS matching must manually populate search_vector.
    Tests for /search/suggestions use ILIKE and work without a tsvector trigger.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media_item import MediaItem
from app.models.media_source import MediaSource


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def source(db_session: AsyncSession) -> MediaSource:
    s = MediaSource(name="Search Source", path="/media/search", source_type="local")
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.fixture
async def items(db_session: AsyncSession, source: MediaSource) -> list[MediaItem]:
    """Creates three media items: two images and one video."""
    records = [
        MediaItem(
            source_id=source.id,
            file_path="/media/search/sunset.jpg",
            filename="sunset.jpg",
            media_type="image",
            mime_type="image/jpeg",
            file_size=2_000_000,
            index_status="indexed",
        ),
        MediaItem(
            source_id=source.id,
            file_path="/media/search/beach.jpg",
            filename="beach.jpg",
            media_type="image",
            mime_type="image/jpeg",
            file_size=1_500_000,
            index_status="indexed",
        ),
        MediaItem(
            source_id=source.id,
            file_path="/media/search/ocean.mp4",
            filename="ocean.mp4",
            media_type="video",
            mime_type="video/mp4",
            file_size=80_000_000,
            duration_seconds=300.0,
            index_status="indexed",
        ),
    ]
    for r in records:
        db_session.add(r)
    await db_session.flush()

    # Manually populate search_vector since the trigger doesn't exist in the
    # test DB (created with create_all, not via Alembic migration).
    #
    # Use the filename stem (no extension) and mime subtype (e.g. "jpeg" not
    # "image/jpeg") so that to_tsvector produces distinct lexemes rather than
    # treating "sunset.jpg" or "image/jpeg" as a single opaque token.
    for r in records:
        stem = r.filename.rsplit(".", 1)[0]          # "sunset.jpg" → "sunset"
        subtype = (r.mime_type or "").split("/")[-1]  # "image/jpeg" → "jpeg"
        await db_session.execute(
            text(
                """
                UPDATE media_items
                SET search_vector =
                    setweight(to_tsvector('english', :stem), 'A') ||
                    setweight(to_tsvector('english', :subtype), 'C')
                WHERE id = :id
                """
            ),
            {"id": r.id, "stem": stem, "subtype": subtype},
        )

    return records


# ── Search endpoint ───────────────────────────────────────────────────────────


async def test_search_returns_200(client):
    resp = await client.get("/api/v1/search?q=test")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 0


async def test_search_requires_q_param(client):
    resp = await client.get("/api/v1/search")
    assert resp.status_code == 422


async def test_search_by_filename_matches(client, items):
    resp = await client.get("/api/v1/search?q=sunset")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["filename"] == "sunset.jpg"


async def test_search_by_mime_type_matches(client, items):
    resp = await client.get("/api/v1/search?q=jpeg")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


async def test_search_filter_by_type(client, items):
    resp = await client.get("/api/v1/search?q=ocean&type=video")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["media_type"] == "video"


async def test_search_filter_by_source(client, source, items):
    resp = await client.get(f"/api/v1/search?q=beach&source_id={source.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1


async def test_search_sort_by_size(client, items):
    resp = await client.get("/api/v1/search?q=jpeg&sort=size&order=desc")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    # Larger item should come first
    assert data["items"][0]["file_size"] >= data["items"][1]["file_size"]


async def test_search_sort_by_name(client, items):
    resp = await client.get("/api/v1/search?q=jpeg&sort=name&order=asc")
    assert resp.status_code == 200
    data = resp.json()
    names = [i["filename"] for i in data["items"]]
    assert names == sorted(names)


async def test_search_pagination(client, items):
    resp = await client.get("/api/v1/search?q=jpeg&page=1&limit=1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["total"] == 2
    assert data["pages"] == 2


async def test_search_requires_auth(client):
    resp = await client.get(
        "/api/v1/search?q=test", headers={"X-API-Token": "bad"}
    )
    assert resp.status_code == 401


# ── Suggestions endpoint ──────────────────────────────────────────────────────


async def test_suggestions_empty(client):
    resp = await client.get("/api/v1/search/suggestions?q=xyz")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_suggestions_returns_matches(client, items):
    resp = await client.get("/api/v1/search/suggestions?q=beach")
    assert resp.status_code == 200
    data = resp.json()
    assert "beach.jpg" in data


async def test_suggestions_partial_match(client, items):
    resp = await client.get("/api/v1/search/suggestions?q=.jpg")
    assert resp.status_code == 200
    data = resp.json()
    # Both .jpg files should appear
    assert len(data) == 2


async def test_suggestions_limit(client, items):
    resp = await client.get("/api/v1/search/suggestions?q=.&limit=1")
    assert resp.status_code == 200
    assert len(resp.json()) <= 1


async def test_suggestions_requires_q(client):
    resp = await client.get("/api/v1/search/suggestions")
    assert resp.status_code == 422


async def test_suggestions_requires_auth(client):
    resp = await client.get(
        "/api/v1/search/suggestions?q=test", headers={"X-API-Token": "bad"}
    )
    assert resp.status_code == 401
