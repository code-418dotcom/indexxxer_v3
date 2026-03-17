"""Downloader API endpoints."""

import os

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.deps import get_current_user

router = APIRouter(prefix="/downloader", tags=["downloader"])

DOWNLOAD_ROOT = "/media/xxx/Downloader"


class DownloadRequest(BaseModel):
    url: str
    subdirectory: str


class DownloadUrlsRequest(BaseModel):
    image_urls: list[str]
    subdirectory: str


class DownloadPreview(BaseModel):
    url: str


@router.post("/preview")
async def preview_gallery(
    body: DownloadPreview,
    _user=Depends(get_current_user),
):
    """Scrape a URL and return the found image URLs without downloading."""
    from app.services.downloader import scrape_image_urls

    try:
        urls = scrape_image_urls(body.url)
    except Exception as e:
        return {"error": str(e), "images": [], "count": 0}

    return {"images": urls, "count": len(urls)}


@router.post("/start")
async def start_download(
    body: DownloadRequest,
    _user=Depends(get_current_user),
):
    """Scrape image URLs here (backend has good TLS), then dispatch download to worker."""
    from app.services.downloader import scrape_image_urls
    from app.workers.tasks.downloader import download_gallery_task

    # Sanitize subdirectory name
    subdir = body.subdirectory.strip().replace("/", "_").replace("\\", "_").replace("..", "_")
    if not subdir:
        return {"error": "Subdirectory name is required"}

    # Scrape in the API process (works reliably here)
    try:
        image_urls = scrape_image_urls(body.url)
    except Exception as e:
        return {"error": f"Failed to scrape: {e}"}

    if not image_urls:
        return {"error": "No images found on page"}

    # Pass pre-scraped URLs to worker for downloading
    result = download_gallery_task.apply_async(
        kwargs={"image_urls": image_urls, "subdirectory": subdir, "source_url": body.url},
        queue="indexing",
    )

    return {"task_id": result.id, "status": "started", "subdirectory": subdir, "image_count": len(image_urls)}


@router.post("/start-urls")
async def start_download_with_urls(
    body: DownloadUrlsRequest,
    _user=Depends(get_current_user),
):
    """Download pre-scraped image URLs (bypass server-side scraping)."""
    from app.workers.tasks.downloader import download_gallery_task

    subdir = body.subdirectory.strip().replace("/", "_").replace("\\", "_").replace("..", "_")
    if not subdir:
        return {"error": "Subdirectory name is required"}
    if not body.image_urls:
        return {"error": "No image URLs provided"}

    result = download_gallery_task.apply_async(
        kwargs={"image_urls": body.image_urls, "subdirectory": subdir, "source_url": ""},
        queue="indexing",
    )

    return {"task_id": result.id, "status": "started", "subdirectory": subdir, "image_count": len(body.image_urls)}


@router.get("/status/{subdirectory}")
async def download_status(
    subdirectory: str,
    _user=Depends(get_current_user),
):
    """Check which files exist in a download subdirectory."""
    path = os.path.join(DOWNLOAD_ROOT, subdirectory)
    if not os.path.exists(path):
        return {"files": [], "count": 0}

    files = [f for f in os.listdir(path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
    return {"files": files, "count": len(files)}


@router.get("/history")
async def download_history(
    _user=Depends(get_current_user),
):
    """List downloaded gallery directories."""
    if not os.path.exists(DOWNLOAD_ROOT):
        return {"directories": []}

    dirs = []
    for name in sorted(os.listdir(DOWNLOAD_ROOT)):
        path = os.path.join(DOWNLOAD_ROOT, name)
        if os.path.isdir(path):
            files = [f for f in os.listdir(path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
            total_size = sum(os.path.getsize(os.path.join(path, f)) for f in files)
            dirs.append({
                "name": name,
                "image_count": len(files),
                "total_size": total_size,
            })

    return {"directories": dirs}
