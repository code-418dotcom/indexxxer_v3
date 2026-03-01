"""Pydantic schemas for MediaSource (create, update, response)."""

from datetime import datetime

from pydantic import BaseModel, Field


class SourceCreate(BaseModel):
    name: str = Field(..., max_length=255)
    path: str
    source_type: str = "local"
    scan_config: dict | None = None


class SourceUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    path: str | None = None
    enabled: bool | None = None
    scan_config: dict | None = None


class SourceResponse(BaseModel):
    id: str
    name: str
    path: str
    source_type: str
    enabled: bool
    scan_config: dict | None = None
    last_scan_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
