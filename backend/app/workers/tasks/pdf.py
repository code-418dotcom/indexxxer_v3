"""
Celery tasks for PDF indexing.

scan_pdfs_task   — walk a source path for .pdf files
index_pdf_task   — index a single PDF: metadata + cover thumbnail
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

import structlog
from sqlalchemy import select

from app.config import settings
from app.models.pdf_document import PDFDocument
from app.workers.celery_app import celery_app
from app.workers.db import task_session

log = structlog.get_logger(__name__)


# ── Task: scan a source path for PDF files ─────────────────────────────────────

@celery_app.task(
    bind=True,
    queue="indexing",
    name="app.workers.tasks.pdf.scan_pdfs_task",
)
def scan_pdfs_task(self, source_id: str, path: str) -> dict:
    """Walk *path* recursively for .pdf files and dispatch index_pdf_task for each."""
    root = Path(path)
    if not root.exists():
        log.error("scan_pdfs.path_missing", path=path)
        return {"error": "path not found"}

    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fname in filenames:
            if fname.lower().endswith(".pdf") and not fname.startswith("."):
                found.append(str(Path(dirpath) / fname))

    log.info("scan_pdfs.found", count=len(found), path=path)

    for pdf_path in found:
        index_pdf_task.apply_async(
            kwargs={"file_path": pdf_path, "source_id": source_id},
            queue="indexing",
        )

    return {"status": "dispatched", "count": len(found)}


# ── Task: index a single PDF ───────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    queue="indexing",
    max_retries=2,
    default_retry_delay=30,
    name="app.workers.tasks.pdf.index_pdf_task",
)
def index_pdf_task(self, file_path: str, source_id: str) -> dict:
    try:
        return asyncio.run(_index_pdf(file_path, source_id))
    except Exception as exc:
        log.error("index_pdf.failed", path=file_path, error=str(exc), exc_info=True)
        raise self.retry(exc=exc)


async def _index_pdf(file_path: str, source_id: str) -> dict:
    fpath = Path(file_path)

    if not fpath.exists():
        log.warning("index_pdf.missing", path=file_path)
        return {"error": "file not found"}

    try:
        stat = fpath.stat()
    except OSError as exc:
        return {"error": str(exc)}

    file_size = stat.st_size
    file_mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

    # Open with pymupdf
    try:
        import fitz
        doc = fitz.open(file_path)
        page_count = len(doc)
        meta = doc.metadata or {}
        title = (meta.get("title") or "").strip() or None
    except Exception as exc:
        log.warning("index_pdf.open_failed", path=file_path, error=str(exc))
        return {"error": str(exc)}

    log.info("index_pdf.start", path=fpath.name, pages=page_count)

    async with task_session() as session:
        result = await session.execute(
            select(PDFDocument).where(PDFDocument.file_path == file_path)
        )
        pdf_doc = result.scalar_one_or_none()

        if pdf_doc is None:
            pdf_doc = PDFDocument(
                source_id=source_id,
                file_path=file_path,
                filename=fpath.stem,
                title=title,
                page_count=page_count,
                file_size=file_size,
                file_mtime=file_mtime,
            )
            session.add(pdf_doc)
        else:
            # Skip if unchanged
            if (
                pdf_doc.file_mtime is not None
                and abs((file_mtime - pdf_doc.file_mtime).total_seconds()) < 2
                and pdf_doc.page_count == page_count
            ):
                return {"pdf_id": pdf_doc.id, "status": "unchanged"}

            pdf_doc.source_id = source_id
            pdf_doc.filename = fpath.stem
            pdf_doc.title = title
            pdf_doc.page_count = page_count
            pdf_doc.file_size = file_size
            pdf_doc.file_mtime = file_mtime

        await session.flush()
        pdf_id = pdf_doc.id

        # Extract cover thumbnail (page 0, small scale)
        cover_dir = settings.thumbnail_root_path / pdf_id[:2]
        cover_dir.mkdir(parents=True, exist_ok=True)
        cover_path = str(cover_dir / f"pdf_{pdf_id}.jpg")
        try:
            page = doc[0]
            mat = fitz.Matrix(0.5, 0.5)  # 36 DPI — small thumbnail
            pix = page.get_pixmap(matrix=mat)
            pix.save(cover_path, output="jpeg", jpg_quality=80)
            pdf_doc.cover_path = cover_path
        except Exception as exc:
            log.warning("index_pdf.cover_failed", path=file_path, error=str(exc))

        doc.close()
        await session.flush()

    log.info("index_pdf.done", pdf_id=pdf_id, pages=page_count)
    return {"pdf_id": pdf_id, "page_count": page_count, "status": "indexed"}
