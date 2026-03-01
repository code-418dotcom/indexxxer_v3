"""
Index job endpoints — list, get, cancel.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import Auth
from app.core.exceptions import not_found
from app.core.pagination import PaginatedResponse, PaginationParams, paginate
from app.database import get_db
from app.models.index_job import IndexJob
from app.schemas.index_job import JobResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=PaginatedResponse[JobResponse])
async def list_jobs(
    source_id: str | None = Query(None),
    job_status: str | None = Query(None, alias="status"),
    params: PaginationParams = Depends(),
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(IndexJob).order_by(IndexJob.created_at.desc())
    if source_id:
        stmt = stmt.where(IndexJob.source_id == source_id)
    if job_status:
        stmt = stmt.where(IndexJob.status == job_status)

    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    jobs = (
        await db.execute(stmt.offset(params.offset).limit(params.limit))
    ).scalars().all()

    return paginate([JobResponse.model_validate(j) for j in jobs], total, params)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(IndexJob, job_id)
    if not job:
        raise not_found("IndexJob", job_id)
    return JobResponse.model_validate(job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_job(
    job_id: str,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    """
    Cancel a pending or running job.
    Running jobs have their Celery task revoked (SIGTERM).
    """
    job = await db.get(IndexJob, job_id)
    if not job:
        raise not_found("IndexJob", job_id)

    if job.status not in ("pending", "running"):
        return  # already terminal — no-op, still 204

    if job.status == "running" and job.celery_task_id:
        from app.workers.celery_app import celery_app

        celery_app.control.revoke(job.celery_task_id, terminate=True, signal="SIGTERM")

    job.status = "cancelled"
    job.completed_at = datetime.now(timezone.utc)
