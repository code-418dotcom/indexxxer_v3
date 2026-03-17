from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pdf_document import PDFDocument
from app.schemas.pdf_document import PDFDocumentSchema


def _to_schema(doc: PDFDocument, api_v1_prefix: str) -> PDFDocumentSchema:
    cover_url = f"{api_v1_prefix}/pdfs/{doc.id}/cover" if doc.cover_path else None
    return PDFDocumentSchema(
        id=doc.id,
        source_id=doc.source_id,
        filename=doc.filename,
        file_path=doc.file_path,
        title=doc.title,
        page_count=doc.page_count,
        file_size=doc.file_size,
        file_mtime=doc.file_mtime.isoformat() if doc.file_mtime else None,
        cover_url=cover_url,
        created_at=doc.created_at.isoformat(),
        updated_at=doc.updated_at.isoformat(),
    )


async def list_pdfs(
    db: AsyncSession,
    api_v1_prefix: str,
    page: int = 1,
    limit: int = 48,
    q: str | None = None,
) -> tuple[list[PDFDocumentSchema], int]:
    offset = (page - 1) * limit

    stmt = select(PDFDocument)
    if q:
        stmt = stmt.where(
            PDFDocument.filename.ilike(f"%{q}%") | PDFDocument.title.ilike(f"%{q}%")
        )

    total_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = total_result.scalar_one()

    result = await db.execute(
        stmt.order_by(PDFDocument.filename).offset(offset).limit(limit)
    )
    docs = result.scalars().all()

    return [_to_schema(d, api_v1_prefix) for d in docs], total


async def get_pdf(
    db: AsyncSession,
    pdf_id: str,
    api_v1_prefix: str,
) -> PDFDocumentSchema | None:
    doc = await db.get(PDFDocument, pdf_id)
    if not doc:
        return None
    return _to_schema(doc, api_v1_prefix)
