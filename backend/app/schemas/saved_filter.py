"""Pydantic schemas for SavedFilter CRUD."""

from datetime import datetime

from pydantic import BaseModel


class FilterCreate(BaseModel):
    name: str
    filters: dict
    is_default: bool = False


class FilterUpdate(BaseModel):
    name: str | None = None
    filters: dict | None = None
    is_default: bool | None = None


class FilterResponse(BaseModel):
    id: str
    name: str
    filters: dict
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
