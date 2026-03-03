"""Pydantic schemas for Tag and TagRef (embedded in media responses)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TagBase(BaseModel):
    name: str = Field(..., max_length=255)
    category: str | None = None
    color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")


class TagCreate(TagBase):
    pass


class TagUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    category: str | None = None
    color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")


class TagRef(BaseModel):
    """Lightweight tag embedded inside MediaItem responses."""

    id: str
    name: str
    slug: str
    category: str | None = None
    color: str | None = None
    confidence: float
    source: Literal["manual", "ai", "filename"]

    model_config = {"from_attributes": True}


class TagResponse(TagBase):
    id: str
    slug: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
