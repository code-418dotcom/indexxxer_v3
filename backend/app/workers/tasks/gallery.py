"""
Celery tasks for gallery indexing.

scan_galleries_task        — walk a source path for ZIP files AND image folders
index_gallery_task         — index a single ZIP as a Gallery
index_folder_gallery_task  — index a directory of images as a Gallery
"""

from __future__ import annotations

import asyncio
import io
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import structlog
from sqlalchemy import delete, select

from app.config import settings
from app.models.gallery import Gallery, GalleryImage
from app.workers.celery_app import celery_app
from app.workers.db import task_session

log = structlog.get_logger(__name__)

_IMAGE_EXTS = frozenset(
    {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif"}
)


def _list_images_in_zip(zf: zipfile.ZipFile) -> list[str]:
    """Return sorted image paths from a ZipFile, skipping directories and hidden files."""
    names = []
    for name in zf.namelist():
        if name.endswith("/"):
            continue
        p = Path(name)
        if p.name.startswith(".") or p.suffix.lower() not in _IMAGE_EXTS:
            continue
        names.append(name)
    return sorted(names)


def _list_images_in_dir(dirpath: Path) -> list[Path]:
    """Return sorted image files that are direct children of *dirpath*."""
    return sorted(
        f
        for f in dirpath.iterdir()
        if f.is_file() and not f.name.startswith(".") and f.suffix.lower() in _IMAGE_EXTS
    )


# ── Task: scan a source path for ZIPs and image folders ───────────────────────

@celery_app.task(
    bind=True,
    queue="indexing",
    name="app.workers.tasks.gallery.scan_galleries_task",
)
def scan_galleries_task(self, source_id: str, path: str) -> dict:
    """Walk *path* for ZIP files and image-containing folders; dispatch indexing tasks."""
    root = Path(path)
    if not root.exists():
        log.error("scan_galleries.path_missing", path=path)
        return {"error": "path not found"}

    zip_count = 0
    folder_count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        current = Path(dirpath)

        # ZIP galleries
        for fname in filenames:
            if fname.lower().endswith(".zip") and not fname.startswith("."):
                index_gallery_task.apply_async(
                    kwargs={"file_path": str(current / fname), "source_id": source_id},
                    queue="indexing",
                )
                zip_count += 1

        # Folder galleries — only directories with more than 5 images
        image_files = [
            f for f in filenames
            if not f.startswith(".") and Path(f).suffix.lower() in _IMAGE_EXTS
        ]
        if len(image_files) > 5:
            index_folder_gallery_task.apply_async(
                kwargs={"folder_path": str(current), "source_id": source_id},
                queue="indexing",
            )
            folder_count += 1

    log.info(
        "scan_galleries.dispatched",
        path=path,
        zip_count=zip_count,
        folder_count=folder_count,
    )
    return {"status": "dispatched", "zip_count": zip_count, "folder_count": folder_count}


# ── Task: index a single ZIP gallery ──────────────────────────────────────────

@celery_app.task(
    bind=True,
    queue="indexing",
    max_retries=2,
    default_retry_delay=30,
    name="app.workers.tasks.gallery.index_gallery_task",
)
def index_gallery_task(self, file_path: str, source_id: str) -> dict:
    try:
        return asyncio.run(_index_zip_gallery(file_path, source_id))
    except Exception as exc:
        log.error("index_gallery.failed", path=file_path, error=str(exc), exc_info=True)
        raise self.retry(exc=exc)


async def _index_zip_gallery(file_path: str, source_id: str) -> dict:
    fpath = Path(file_path)

    if not fpath.exists():
        log.warning("index_gallery.missing", path=file_path)
        return {"error": "file not found"}

    try:
        stat = fpath.stat()
    except OSError as exc:
        return {"error": str(exc)}

    file_size = stat.st_size
    file_mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            names = _list_images_in_zip(zf)
    except zipfile.BadZipFile:
        log.warning("index_gallery.bad_zip", path=file_path)
        return {"error": "bad zip file"}

    image_count = len(names)
    log.info("index_gallery.start", path=fpath.name, images=image_count)

    async with task_session() as session:
        result = await session.execute(
            select(Gallery).where(Gallery.file_path == file_path)
        )
        gallery = result.scalar_one_or_none()

        if gallery is None:
            gallery = Gallery(
                source_id=source_id,
                file_path=file_path,
                filename=fpath.stem,
                image_count=image_count,
                file_size=file_size,
                file_mtime=file_mtime,
            )
            session.add(gallery)
        else:
            if (
                gallery.file_mtime is not None
                and abs((file_mtime - gallery.file_mtime).total_seconds()) < 2
                and gallery.image_count == image_count
            ):
                return {"gallery_id": gallery.id, "status": "unchanged"}

            gallery.source_id = source_id
            gallery.filename = fpath.stem
            gallery.image_count = image_count
            gallery.file_size = file_size
            gallery.file_mtime = file_mtime

        await session.flush()
        gallery_id = gallery.id

        if names:
            cover_dir = settings.thumbnail_root_path / gallery_id[:2]
            cover_dir.mkdir(parents=True, exist_ok=True)
            cover_path = str(cover_dir / f"g_{gallery_id}.jpg")
            try:
                from PIL import Image as PILImage
                with zipfile.ZipFile(file_path, "r") as zf:
                    with zf.open(names[0]) as img_file:
                        img = PILImage.open(io.BytesIO(img_file.read())).convert("RGB")
                        img.thumbnail((400, 400))
                        img.save(cover_path, format="JPEG", quality=85)
                gallery.cover_path = cover_path
            except Exception as exc:
                log.warning("index_gallery.cover_failed", path=file_path, error=str(exc))

        await session.execute(
            delete(GalleryImage).where(GalleryImage.gallery_id == gallery_id)
        )
        for i, name in enumerate(names):
            session.add(GalleryImage(gallery_id=gallery_id, filename=name, index_order=i))

        await session.flush()

    log.info("index_gallery.done", gallery_id=gallery_id, images=image_count)
    return {"gallery_id": gallery_id, "image_count": image_count, "status": "indexed"}


# ── Task: index a folder of images as a gallery ────────────────────────────────

@celery_app.task(
    bind=True,
    queue="indexing",
    max_retries=2,
    default_retry_delay=30,
    name="app.workers.tasks.gallery.index_folder_gallery_task",
)
def index_folder_gallery_task(self, folder_path: str, source_id: str) -> dict:
    try:
        return asyncio.run(_index_folder_gallery(folder_path, source_id))
    except Exception as exc:
        log.error(
            "index_folder_gallery.failed",
            path=folder_path,
            error=str(exc),
            exc_info=True,
        )
        raise self.retry(exc=exc)


async def _index_folder_gallery(folder_path: str, source_id: str) -> dict:
    fpath = Path(folder_path)

    if not fpath.is_dir():
        return {"error": "not a directory"}

    images = _list_images_in_dir(fpath)
    if not images:
        return {"status": "skipped", "reason": "no images"}

    image_count = len(images)
    try:
        stat = fpath.stat()
        file_mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    except OSError:
        file_mtime = None

    log.info("index_folder_gallery.start", path=fpath.name, images=image_count)

    async with task_session() as session:
        result = await session.execute(
            select(Gallery).where(Gallery.file_path == folder_path)
        )
        gallery = result.scalar_one_or_none()

        if gallery is None:
            gallery = Gallery(
                source_id=source_id,
                file_path=folder_path,
                filename=fpath.name,
                image_count=image_count,
                file_mtime=file_mtime,
            )
            session.add(gallery)
        else:
            if (
                gallery.file_mtime is not None
                and file_mtime is not None
                and abs((file_mtime - gallery.file_mtime).total_seconds()) < 2
                and gallery.image_count == image_count
            ):
                return {"gallery_id": gallery.id, "status": "unchanged"}

            gallery.source_id = source_id
            gallery.filename = fpath.name
            gallery.image_count = image_count
            gallery.file_mtime = file_mtime

        await session.flush()
        gallery_id = gallery.id

        # Cover from first image (read directly from filesystem)
        cover_dir = settings.thumbnail_root_path / gallery_id[:2]
        cover_dir.mkdir(parents=True, exist_ok=True)
        cover_path = str(cover_dir / f"g_{gallery_id}.jpg")
        try:
            from PIL import Image as PILImage
            img = PILImage.open(images[0]).convert("RGB")
            img.thumbnail((400, 400))
            img.save(cover_path, format="JPEG", quality=85)
            gallery.cover_path = cover_path
        except Exception as exc:
            log.warning("index_folder_gallery.cover_failed", path=folder_path, error=str(exc))

        # Store absolute filesystem path as filename (distinguishes from ZIP entries)
        await session.execute(
            delete(GalleryImage).where(GalleryImage.gallery_id == gallery_id)
        )
        for i, img_path in enumerate(images):
            session.add(
                GalleryImage(
                    gallery_id=gallery_id,
                    filename=str(img_path),  # absolute path on disk
                    index_order=i,
                )
            )

        await session.flush()

    log.info("index_folder_gallery.done", gallery_id=gallery_id, images=image_count)
    return {"gallery_id": gallery_id, "image_count": image_count, "status": "indexed"}
