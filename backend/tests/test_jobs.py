"""
Tests for GET/DELETE /jobs and GET /jobs/{id} endpoints.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.index_job import IndexJob
from app.models.media_source import MediaSource


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def source(db_session: AsyncSession) -> MediaSource:
    s = MediaSource(name="Job Source", path="/media/jobs", source_type="local")
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.fixture
async def pending_job(db_session: AsyncSession, source: MediaSource) -> IndexJob:
    job = IndexJob(
        source_id=source.id,
        job_type="full",
        status="pending",
    )
    db_session.add(job)
    await db_session.flush()
    return job


@pytest.fixture
async def running_job(db_session: AsyncSession, source: MediaSource) -> IndexJob:
    job = IndexJob(
        source_id=source.id,
        job_type="full",
        status="running",
        total_files=100,
        processed_files=42,
        failed_files=1,
        skipped_files=5,
        started_at=datetime.now(timezone.utc),
        celery_task_id="celery-abc-123",
    )
    db_session.add(job)
    await db_session.flush()
    return job


@pytest.fixture
async def completed_job(db_session: AsyncSession, source: MediaSource) -> IndexJob:
    job = IndexJob(
        source_id=source.id,
        job_type="incremental",
        status="completed",
        total_files=10,
        processed_files=10,
        failed_files=0,
        skipped_files=0,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(job)
    await db_session.flush()
    return job


# ── List jobs ─────────────────────────────────────────────────────────────────


async def test_list_jobs_empty(client):
    resp = await client.get("/api/v1/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_list_jobs_returns_jobs(client, pending_job, completed_job):
    resp = await client.get("/api/v1/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


async def test_list_jobs_filter_by_status(client, pending_job, completed_job):
    resp = await client.get("/api/v1/jobs?status=pending")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "pending"


async def test_list_jobs_filter_by_source(client, source, pending_job):
    resp = await client.get(f"/api/v1/jobs?source_id={source.id}")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


async def test_list_jobs_requires_auth(client):
    resp = await client.get("/api/v1/jobs", headers={"X-API-Token": "bad"})
    assert resp.status_code == 401


# ── Get job ───────────────────────────────────────────────────────────────────


async def test_get_job(client, running_job):
    resp = await client.get(f"/api/v1/jobs/{running_job.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == running_job.id
    assert data["status"] == "running"
    assert data["total_files"] == 100
    assert data["processed_files"] == 42


async def test_get_job_not_found(client):
    resp = await client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ── Cancel job ────────────────────────────────────────────────────────────────


async def test_cancel_pending_job(client, pending_job):
    resp = await client.delete(f"/api/v1/jobs/{pending_job.id}")
    assert resp.status_code == 204


async def test_cancel_completed_job_is_noop(client, completed_job):
    # Cancelling a terminal job returns 204 but doesn't change status
    resp = await client.delete(f"/api/v1/jobs/{completed_job.id}")
    assert resp.status_code == 204


async def test_cancel_job_not_found(client):
    resp = await client.delete("/api/v1/jobs/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_cancel_running_job_revokes_celery(client, running_job):
    from unittest.mock import patch

    with patch("app.workers.celery_app.celery_app.control.revoke") as mock_revoke:
        resp = await client.delete(f"/api/v1/jobs/{running_job.id}")
    assert resp.status_code == 204
    mock_revoke.assert_called_once_with(
        "celery-abc-123", terminate=True, signal="SIGTERM"
    )
