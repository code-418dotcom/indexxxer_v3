"""
Export endpoint — stream media library as CSV or JSON.

GET /export?format=csv|json[&type=...&source_id=...&tag_ids=...&favourite=true]

CSV columns: id, filename, file_path, media_type, mime_type, file_size, tags, indexed_at
JSON: array of the same fields.

Streams inline — suitable for ≤200 k items without OOM risk.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import AsyncGenerator
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import Auth
from app.database import get_db
from app.models.media_item import MediaItem
from app.models.tag import MediaTag

router = APIRouter(prefix="/export", tags=["export"])

_CSV_FIELDS = [
    "id",
    "filename",
    "file_path",
    "media_type",
    "mime_type",
    "file_size",
    "tags",
    "indexed_at",
]


def _build_query(
    *,
    media_type: str | None,
    source_id: str | None,
    tag_ids: list[str] | None,
    favourite: bool | None,
):
    stmt = select(MediaItem).options(
        selectinload(MediaItem.media_tags).selectinload(MediaTag.tag)
    )
    if media_type:
        stmt = stmt.where(MediaItem.media_type == media_type)
    if source_id:
        stmt = stmt.where(MediaItem.source_id == source_id)
    if favourite is not None:
        stmt = stmt.where(MediaItem.is_favourite == favourite)
    if tag_ids:
        for tid in tag_ids:
            stmt = stmt.where(
                MediaItem.id.in_(
                    select(MediaTag.media_id).where(MediaTag.tag_id == tid)
                )
            )
    return stmt.order_by(MediaItem.indexed_at.desc().nulls_last())


def _item_to_dict(item: MediaItem) -> dict:
    tag_names = ",".join(mt.tag.name for mt in item.media_tags if mt.tag)
    return {
        "id": item.id,
        "filename": item.filename,
        "file_path": item.file_path,
        "media_type": item.media_type or "",
        "mime_type": item.mime_type or "",
        "file_size": item.file_size or 0,
        "tags": tag_names,
        "indexed_at": item.indexed_at.isoformat() if item.indexed_at else "",
    }


async def _stream_csv(db: AsyncSession, stmt) -> AsyncGenerator[str, None]:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    yield buf.getvalue()

    # Stream in batches of 500
    BATCH = 500
    offset = 0
    while True:
        rows = (
            await db.execute(stmt.offset(offset).limit(BATCH))
        ).scalars().all()
        if not rows:
            break
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=_CSV_FIELDS, lineterminator="\n")
        for item in rows:
            writer.writerow(_item_to_dict(item))
        yield buf.getvalue()
        offset += BATCH
        if len(rows) < BATCH:
            break


async def _stream_json(db: AsyncSession, stmt) -> AsyncGenerator[str, None]:
    yield "[\n"
    BATCH = 500
    offset = 0
    first = True
    while True:
        rows = (
            await db.execute(stmt.offset(offset).limit(BATCH))
        ).scalars().all()
        if not rows:
            break
        for item in rows:
            prefix = "" if first else ",\n"
            yield prefix + json.dumps(_item_to_dict(item))
            first = False
        offset += BATCH
        if len(rows) < BATCH:
            break
    yield "\n]\n"


@router.get("")
async def export_media(
    format: str = Query(default="csv", description="csv | json"),
    type: str | None = Query(None, description="image | video"),
    source_id: str | None = Query(None),
    tag_ids: list[str] = Query(default=[]),
    favourite: bool | None = Query(None),
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    stmt = _build_query(
        media_type=type,
        source_id=source_id,
        tag_ids=tag_ids or None,
        favourite=favourite,
    )
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    if format == "json":
        return StreamingResponse(
            _stream_json(db, stmt),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="export_{ts}.json"'},
        )

    return StreamingResponse(
        _stream_csv(db, stmt),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="export_{ts}.csv"'},
    )
