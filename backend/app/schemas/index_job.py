"""Pydantic schemas for IndexJob (scan trigger, job status response)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ScanRequest(BaseModel):
    job_type: Literal["full", "incremental"] = "full"


class JobResponse(BaseModel):
    id: str
    source_id: str
    job_type: str
    status: str
    total_files: int | None = None
    processed_files: int
    failed_files: int
    skipped_files: int
    celery_task_id: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
