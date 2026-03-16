"""Celery task for downloading gallery images."""

from __future__ import annotations

import structlog
from app.workers.celery_app import celery_app
from app.services.downloader import download_images
from app.workers.events import emit

log = structlog.get_logger(__name__)

DOWNLOAD_ROOT = "/media/xxx/Downloader"


@celery_app.task(
    bind=True,
    queue="indexing",
    name="app.workers.tasks.downloader.download_gallery_task",
)
def download_gallery_task(
    self,
    image_urls: list[str],
    subdirectory: str,
    source_url: str = "",
    job_id: str | None = None,
) -> dict:
    """Download pre-scraped image URLs to a subdirectory."""
    dest_dir = f"{DOWNLOAD_ROOT}/{subdirectory}"

    log.info("downloader.start", url=source_url, dest=dest_dir, count=len(image_urls))
    if job_id:
        emit(job_id, "download.start", url=source_url, dest=dest_dir)
        emit(job_id, "download.discovered", total=len(image_urls))

    def on_progress(current, total, filename, status):
        if job_id:
            emit(job_id, "download.progress", current=current, total=total, filename=filename, status=status)

    result = download_images(image_urls, dest_dir, on_progress=on_progress)
    result["status"] = "done"
    result["url"] = source_url
    result["directory"] = subdirectory

    log.info("downloader.complete", **result)
    if job_id:
        emit(job_id, "download.complete", **result)

    return result
