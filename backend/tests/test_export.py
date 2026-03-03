"""
Export endpoint tests.

GET /export?format=csv|json[&type=...&source_id=...&favourite=true]
"""

import csv
import io
import json

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import new_uuid
from app.models.media_item import MediaItem
from app.models.media_source import MediaSource


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _make_source(db: AsyncSession) -> MediaSource:
    src = MediaSource(
        id=new_uuid(), name="export_test", path="/media/export", source_type="local"
    )
    db.add(src)
    await db.flush()
    return src


async def _make_item(
    db: AsyncSession,
    source_id: str,
    filename: str = "test.jpg",
    media_type: str = "image",
    mime_type: str = "image/jpeg",
    is_favourite: bool = False,
) -> MediaItem:
    item = MediaItem(
        id=new_uuid(),
        source_id=source_id,
        file_path=f"/media/export/{filename}",
        filename=filename,
        media_type=media_type,
        mime_type=mime_type,
        file_size=1024,
        index_status="indexed",
        is_favourite=is_favourite,
        clip_status="pending",
    )
    db.add(item)
    await db.flush()
    return item


# ── CSV format ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_export_csv_basic(client: AsyncClient, db_session: AsyncSession):
    src = await _make_source(db_session)
    await _make_item(db_session, src.id, filename="photo.jpg")

    r = await client.get("/api/v1/export", params={"format": "csv"})
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "attachment" in r.headers.get("content-disposition", "")

    reader = csv.DictReader(io.StringIO(r.text))
    rows = list(reader)
    assert len(rows) >= 1
    assert rows[0]["filename"] == "photo.jpg"


@pytest.mark.asyncio
async def test_export_csv_columns(client: AsyncClient, db_session: AsyncSession):
    """All expected columns present in CSV header."""
    src = await _make_source(db_session)
    await _make_item(db_session, src.id)

    r = await client.get("/api/v1/export", params={"format": "csv"})
    reader = csv.DictReader(io.StringIO(r.text))
    expected = {"id", "filename", "file_path", "media_type", "mime_type", "file_size", "tags", "indexed_at"}
    assert expected.issubset(set(reader.fieldnames or []))


@pytest.mark.asyncio
async def test_export_csv_empty(client: AsyncClient, db_session: AsyncSession):
    """Empty library → CSV with just the header row."""
    r = await client.get("/api/v1/export", params={"format": "csv"})
    assert r.status_code == 200
    reader = csv.DictReader(io.StringIO(r.text))
    assert list(reader) == []


# ── JSON format ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_export_json_basic(client: AsyncClient, db_session: AsyncSession):
    src = await _make_source(db_session)
    await _make_item(db_session, src.id, filename="clip.mp4", media_type="video")

    r = await client.get("/api/v1/export", params={"format": "json"})
    assert r.status_code == 200
    assert "application/json" in r.headers["content-type"]

    data = json.loads(r.text)
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["filename"] == "clip.mp4"
    assert data[0]["media_type"] == "video"


@pytest.mark.asyncio
async def test_export_json_empty(client: AsyncClient, db_session: AsyncSession):
    r = await client.get("/api/v1/export", params={"format": "json"})
    assert r.status_code == 200
    assert json.loads(r.text) == []


# ── Filters ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_export_filter_by_type(client: AsyncClient, db_session: AsyncSession):
    src = await _make_source(db_session)
    await _make_item(db_session, src.id, filename="img.jpg", media_type="image")
    await _make_item(db_session, src.id, filename="vid.mp4", media_type="video")

    r = await client.get("/api/v1/export", params={"format": "json", "type": "image"})
    data = json.loads(r.text)
    assert all(i["media_type"] == "image" for i in data)
    filenames = [i["filename"] for i in data]
    assert "img.jpg" in filenames
    assert "vid.mp4" not in filenames


@pytest.mark.asyncio
async def test_export_filter_favourites(client: AsyncClient, db_session: AsyncSession):
    src = await _make_source(db_session)
    await _make_item(db_session, src.id, filename="fav.jpg", is_favourite=True)
    await _make_item(db_session, src.id, filename="normal.jpg", is_favourite=False)

    r = await client.get("/api/v1/export", params={"format": "json", "favourite": "true"})
    data = json.loads(r.text)
    assert len(data) == 1
    assert data[0]["filename"] == "fav.jpg"


@pytest.mark.asyncio
async def test_export_filter_source(client: AsyncClient, db_session: AsyncSession):
    src1 = await _make_source(db_session)
    src2 = MediaSource(
        id=new_uuid(), name="other", path="/media/other", source_type="local"
    )
    db_session.add(src2)
    await db_session.flush()

    await _make_item(db_session, src1.id, filename="from_src1.jpg")
    await _make_item(db_session, src2.id, filename="from_src2.jpg")

    r = await client.get(
        "/api/v1/export", params={"format": "json", "source_id": src1.id}
    )
    data = json.loads(r.text)
    assert all(i["file_path"].startswith("/media/export/") for i in data)
    filenames = [i["filename"] for i in data]
    assert "from_src1.jpg" in filenames
    assert "from_src2.jpg" not in filenames


# ── Auth ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_export_requires_auth(client: AsyncClient):
    """Without auth header, should get 401/403."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as unauthenticated:
        r = await unauthenticated.get("/api/v1/export")
        assert r.status_code in (401, 403)
