from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, new_uuid


class PDFDocument(Base, TimestampMixin):
    """A PDF file indexed for page-by-page browsing."""

    __tablename__ = "pdf_documents"
    __table_args__ = (
        UniqueConstraint("file_path", name="uq_pdf_path"),
        Index("idx_pdf_source", "source_id"),
        Index("idx_pdf_mtime", "file_mtime"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    source_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("media_sources.id", ondelete="SET NULL"),
        nullable=True,
    )

    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cover_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    file_mtime: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
