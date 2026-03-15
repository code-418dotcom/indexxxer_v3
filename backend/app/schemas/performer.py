"""Pydantic schemas for Performer and PerformerRef (embedded in media responses)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PerformerBase(BaseModel):
    name: str = Field(..., max_length=255)
    aliases: list[str] | None = None
    bio: str | None = None
    birthdate: str | None = None
    birthplace: str | None = None
    nationality: str | None = None
    ethnicity: str | None = None
    hair_color: str | None = None
    eye_color: str | None = None
    height: str | None = None
    weight: str | None = None
    measurements: str | None = None
    years_active: str | None = None


class PerformerCreate(PerformerBase):
    # Optionally provide a freeones URL to trigger scraping
    freeones_url: str | None = None


class PerformerUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    aliases: list[str] | None = None
    bio: str | None = None
    birthdate: str | None = None
    birthplace: str | None = None
    nationality: str | None = None
    ethnicity: str | None = None
    hair_color: str | None = None
    eye_color: str | None = None
    height: str | None = None
    weight: str | None = None
    measurements: str | None = None
    years_active: str | None = None
    freeones_url: str | None = None


class PerformerRef(BaseModel):
    """Lightweight performer ref embedded inside MediaItem responses."""

    id: str
    name: str
    slug: str
    profile_image_url: str | None = None
    match_source: Literal["manual", "filename", "directory"]
    confidence: float

    model_config = {"from_attributes": True}


class PerformerResponse(PerformerBase):
    id: str
    slug: str
    profile_image_url: str | None = None
    freeones_url: str | None = None
    scraped_at: datetime | None = None
    media_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PerformerDetailResponse(PerformerResponse):
    """Full detail view with all fields."""
    pass


class ScrapeRequest(BaseModel):
    """Request body for triggering a scrape by name or URL."""
    name: str | None = None
    freeones_url: str | None = None
