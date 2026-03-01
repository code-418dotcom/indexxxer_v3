"""
MediaSource CRUD + scan orchestration service.

trigger_scan() creates an IndexJob row, then dispatches scan_source_task via Celery.
"""

from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import not_found
from app.models.index_job import IndexJob
from app.models.media_source import MediaSource
from app.schemas.index_job import JobResponse, ScanRequest
from app.schemas.media_source import SourceCreate, SourceResponse, SourceUpdate

log = structlog.get_logger(__name__)


async def list_sources(db: AsyncSession) -> list[SourceResponse]:
    rows = (
        await db.execute(select(MediaSource).order_by(MediaSource.created_at))
    ).scalars().all()
    return [SourceResponse.model_validate(r) for r in rows]


async def create_source(db: AsyncSession, data: SourceCreate) -> SourceResponse:
    source = MediaSource(
        name=data.name,
        path=data.path,
        source_type=data.source_type,
        scan_config=data.scan_config,
    )
    db.add(source)
    await db.flush()
    await db.refresh(source)
    return SourceResponse.model_validate(source)


async def get_source(db: AsyncSession, source_id: str) -> SourceResponse:
    source = await db.get(MediaSource, source_id)
    if not source:
        raise not_found("MediaSource", source_id)
    return SourceResponse.model_validate(source)


async def update_source(
    db: AsyncSession, source_id: str, data: SourceUpdate
) -> SourceResponse:
    source = await db.get(MediaSource, source_id)
    if not source:
        raise not_found("MediaSource", source_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    await db.flush()
    await db.refresh(source)
    return SourceResponse.model_validate(source)


async def delete_source(db: AsyncSession, source_id: str) -> None:
    source = await db.get(MediaSource, source_id)
    if not source:
        raise not_found("MediaSource", source_id)
    await db.delete(source)


async def trigger_scan(
    db: AsyncSession, source_id: str, req: ScanRequest
) -> JobResponse:
    source = await db.get(MediaSource, source_id)
    if not source:
        raise not_found("MediaSource", source_id)

    job = IndexJob(
        source_id=source_id,
        job_type=req.job_type,
        status="pending",
    )
    db.add(job)
    await db.flush()  # get job.id

    # Dispatch Celery task (import here to avoid circular imports at module load)
    from app.workers.tasks.scan import scan_source_task

    result = scan_source_task.apply_async(
        kwargs={"source_id": source_id, "job_id": job.id},
        queue="indexing",
    )
    job.celery_task_id = result.id
    source.last_scan_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(job)

    log.info("scan.triggered", source_id=source_id, job_id=job.id, job_type=req.job_type)
    return JobResponse.model_validate(job)
