from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid


class Gallery(Base, TimestampMixin):
    """A ZIP archive containing an image gallery."""

    __tablename__ = "galleries"
    __table_args__ = (
        UniqueConstraint("file_path", name="uq_gallery_path"),
        Index("idx_gallery_source", "source_id"),
        Index("idx_gallery_mtime", "file_mtime"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    source_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("media_sources.id", ondelete="SET NULL"),
        nullable=True,
    )

    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    image_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cover_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    file_mtime: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Deduplication ──────────────────────────────────────────────────────
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duplicate_group: Mapped[str | None] = mapped_column(String(36), nullable=True)
    dedup_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )

    images: Mapped[list["GalleryImage"]] = relationship(
        back_populates="gallery",
        lazy="noload",
        cascade="all, delete-orphan",
        order_by="GalleryImage.index_order",
    )


class GalleryImage(Base):
    """A single image entry within a Gallery ZIP."""

    __tablename__ = "gallery_images"
    __table_args__ = (
        Index("idx_gi_gallery", "gallery_id"),
        Index("idx_gi_order", "gallery_id", "index_order"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    gallery_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("galleries.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)  # path inside ZIP
    index_order: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    phash: Mapped[str | None] = mapped_column(String(16), nullable=True)

    gallery: Mapped["Gallery"] = relationship(back_populates="images", lazy="noload")
