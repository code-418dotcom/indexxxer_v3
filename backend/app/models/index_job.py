from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid


class IndexJob(Base, TimestampMixin):
    """
    Represents a single scan invocation for a MediaSource.

    Statuses: pending → running → completed | failed | cancelled
    Job types: full (re-index everything) | incremental (new/changed only) | rehash
    """

    __tablename__ = "index_jobs"
    __table_args__ = (
        Index("idx_job_source", "source_id"),
        Index("idx_job_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("media_sources.id", ondelete="CASCADE"),
        nullable=False,
    )

    job_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="full"
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending"
    )

    total_files: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Celery task group ID (for progress tracking)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    source: Mapped["MediaSource"] = relationship(  # noqa: F821
        back_populates="index_jobs", lazy="noload"
    )
