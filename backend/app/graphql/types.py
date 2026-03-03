"""
Strawberry GraphQL type definitions.
These mirror existing Pydantic response schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import strawberry


@strawberry.type
class TagGQL:
    id: str
    name: str
    slug: str
    color: Optional[str] = None


@strawberry.type
class MediaItemGQL:
    id: str
    filename: str
    media_type: str
    file_path: str
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[float] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    is_favourite: bool = False
    caption: Optional[str] = None
    caption_status: Optional[str] = None
    summary: Optional[str] = None
    face_count: int = 0
    created_at: datetime
    thumbnail_url: Optional[str] = None
    tags: list[TagGQL] = strawberry.field(default_factory=list)


@strawberry.type
class MediaSourceGQL:
    id: str
    name: str
    path: str
    source_type: str
    enabled: bool
    last_scan_at: Optional[datetime] = None


@strawberry.type
class IndexJobGQL:
    id: str
    status: str
    total_files: Optional[int] = None
    processed_files: int = 0
    error_files: int = 0
    created_at: datetime


@strawberry.type
class FaceClusterGQL:
    cluster_id: int
    member_count: int
    representative_thumbnail_url: Optional[str] = None


@strawberry.type
class AnalyticsOverviewGQL:
    total_media: int
    total_sources: int
    storage_bytes: int
    face_count: int
    cluster_count: int


@strawberry.type
class SearchResultGQL:
    items: list[MediaItemGQL]
    total: int


@strawberry.input
class SearchInput:
    query: str
    mode: Optional[str] = "auto"
    limit: Optional[int] = 20
    offset: Optional[int] = 0
