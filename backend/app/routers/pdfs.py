"""
PDF browsing endpoints.

GET  /pdfs                  — paginated list of indexed PDFs
GET  /pdfs/{id}             — PDF metadata
GET  /pdfs/{id}/cover       — cover image (page 0 thumbnail, no auth)
GET  /pdfs/{id}/pages/{n}   — render page N as JPEG on-the-fly (no auth, 0-based)
POST /pdfs/scan             — queue scan for all enabled local sources
"""

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import Auth
from app.database import get_db
from app.models.pdf_document import PDFDocument
from app.schemas.pdf_document import PDFDocumentSchema
from app.services import pdf_service

router = APIRouter(tags=["pdfs"])

# Render at 2× (144 DPI) — good balance of quality vs speed
_RENDER_SCALE = 2.0


def _render_page(file_path: str, page_num: int, scale: float = _RENDER_SCALE) -> bytes:
    import fitz  # pymupdf
    doc = fitz.open(file_path)
    if page_num < 0 or page_num >= len(doc):
        raise IndexError(f"Page {page_num} out of range (0–{len(doc) - 1})")
    page = doc[page_num]
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat)
    return pix.tobytes("jpeg", jpg_quality=85)


@router.get("/pdfs", response_model=dict)
async def list_pdfs(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=48, ge=1, le=200),
    q: str | None = Query(default=None),
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
) -> dict:
    items, total = await pdf_service.list_pdfs(
        db, api_v1_prefix=settings.api_v1_prefix, page=page, limit=limit, q=q
    )
    pages = (total + limit - 1) // limit
    return {
        "items": [i.model_dump() for i in items],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


@router.get("/pdfs/{pdf_id}", response_model=PDFDocumentSchema)
async def get_pdf(
    pdf_id: str = Path(...),
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
) -> PDFDocumentSchema:
    doc = await pdf_service.get_pdf(db, pdf_id=pdf_id, api_v1_prefix=settings.api_v1_prefix)
    if not doc:
        raise HTTPException(status_code=404, detail="PDF not found")
    return doc


@router.get("/pdfs/{pdf_id}/cover")
async def get_pdf_cover(
    pdf_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Serve the pre-generated cover thumbnail (no auth)."""
    doc = await db.get(PDFDocument, pdf_id)
    if not doc or not doc.cover_path:
        raise HTTPException(status_code=404, detail="Cover not found")
    try:
        data = open(doc.cover_path, "rb").read()
    except OSError:
        raise HTTPException(status_code=404, detail="Cover file missing")
    return Response(content=data, media_type="image/jpeg")


@router.get("/pdfs/{pdf_id}/pages/{page_num}")
async def get_pdf_page(
    pdf_id: str = Path(...),
    page_num: int = Path(..., ge=0),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Render PDF page *page_num* (0-based) as JPEG on-the-fly (no auth)."""
    doc = await db.get(PDFDocument, pdf_id)
    if not doc:
        raise HTTPException(status_code=404, detail="PDF not found")
    try:
        data = _render_page(doc.file_path, page_num)
    except IndexError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Render failed: {exc}")
    return Response(content=data, media_type="image/jpeg")


@router.post("/pdfs/scan", status_code=202)
async def trigger_pdf_scan(
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Queue PDF scanning for all enabled local sources."""
    from sqlalchemy import select
    from app.models.media_source import MediaSource

    result = await db.execute(
        select(MediaSource).where(
            MediaSource.enabled == True,  # noqa: E712
            MediaSource.source_type == "local",
        )
    )
    sources = result.scalars().all()

    if not sources:
        return {"status": "no_sources", "queued": 0}

    from app.workers.tasks.pdf import scan_pdfs_task

    task_ids = []
    for source in sources:
        task = scan_pdfs_task.apply_async(
            kwargs={"source_id": source.id, "path": source.path},
            queue="indexing",
        )
        task_ids.append(task.id)

    return {"status": "queued", "sources": len(sources), "task_ids": task_ids}
