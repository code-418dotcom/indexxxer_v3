"""Pydantic schemas for MediaItem (list summary, full detail, patch, bulk)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.performer import PerformerRef
from app.schemas.tag import TagRef


class MediaItemSummary(BaseModel):
    """Returned in paginated list and search responses."""

    id: str
    source_id: str
    filename: str
    file_path: str
    media_type: str | None = None
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    file_size: int | None = None
    thumbnail_url: str | None = None  # /api/v1/media/{id}/thumbnail (only if thumbnail exists)
    tags: list[TagRef] = []
    index_status: str
    indexed_at: datetime | None = None
    is_favourite: bool = False
    clip_status: str = "pending"
    # M3 AI status fields (summary-level — no full text in list view)
    caption: str | None = None
    caption_status: str = "pending"
    transcript_status: str = "pending"
    summary_status: str = "pending"
    face_count: int = 0
    performers: list[PerformerRef] = []
    duplicate_group: str | None = None

    model_config = {"from_attributes": True}


class MediaItemDetail(MediaItemSummary):
    """Full detail view — adds codec, hash, timestamps, and full AI text."""

    bitrate: int | None = None
    codec: str | None = None
    frame_rate: float | None = None
    file_hash: str | None = None
    file_mtime: datetime | None = None
    index_error: str | None = None
    created_at: datetime
    updated_at: datetime
    # M3: full text fields (omitted from list view for bandwidth)
    transcript: str | None = None
    summary: str | None = None
    perceptual_hash: str | None = None


class TagOp(BaseModel):
    id: str
    op: Literal["add", "remove"]


class MediaItemPatch(BaseModel):
    filename: str | None = None
    tags: list[TagOp] | None = None
    is_favourite: bool | None = None


class BulkActionRequest(BaseModel):
    ids: list[str]
    action: Literal["add_tags", "remove_tags", "delete"]
    payload: dict | None = None  # e.g. {"tag_ids": ["uuid", ...]}


class BulkResult(BaseModel):
    processed: int
    failed: int
    errors: list[str] = []
