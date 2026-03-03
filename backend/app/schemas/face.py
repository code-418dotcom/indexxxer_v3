"""Pydantic schemas for face detection and cluster endpoints."""

from datetime import datetime

from pydantic import BaseModel


class FaceSchema(BaseModel):
    id: str
    media_id: str
    cluster_id: int | None = None
    bbox_x: int
    bbox_y: int
    bbox_w: int
    bbox_h: int
    confidence: float
    created_at: datetime

    model_config = {"from_attributes": True}


class FaceClusterSchema(BaseModel):
    """Summary of a face cluster — one representative image + member count."""

    cluster_id: int
    member_count: int
    representative_media_id: str | None = None
    # Cropped face thumbnail (preferred); falls back to full media thumbnail
    representative_face_id: str | None = None
    face_crop_url: str | None = None
    representative_thumbnail_url: str | None = None


class FaceClusterMediaResponse(BaseModel):
    """Paginated media IDs for a specific face cluster."""

    cluster_id: int
    media_ids: list[str]
    total: int
    page: int
    limit: int
    pages: int


class FaceStatsSchema(BaseModel):
    """Aggregate face detection and clustering stats."""

    total_faces: int
    unclustered: int
    cluster_count: int
