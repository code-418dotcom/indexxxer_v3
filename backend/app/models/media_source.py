from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid


class MediaSource(Base, TimestampMixin):
    """
    A directory (or future remote mount) that the scanner indexes.
    M1: source_type is always 'local'.
    """

    __tablename__ = "media_sources"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=new_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Absolute path on the host (e.g. /mnt/e/media/xxx → /media/xxx inside container)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="local"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # JSONB blob: {include_globs: [...], exclude_globs: [...], max_depth: int}
    scan_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_scan_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    media_items: Mapped[list["MediaItem"]] = relationship(  # noqa: F821
        back_populates="source", lazy="noload", cascade="all, delete-orphan"
    )
    index_jobs: Mapped[list["IndexJob"]] = relationship(  # noqa: F821
        back_populates="source", lazy="noload", cascade="all, delete-orphan"
    )
