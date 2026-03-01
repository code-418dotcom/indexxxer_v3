from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid


class Tag(Base, TimestampMixin):
    """A label that can be applied to media items."""

    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_tag_slug"),
        Index("idx_tag_category", "category"),
        Index("idx_tag_name", "name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # URL-safe, lowercased, normalised version of name (e.g. "Jane Doe" → "jane-doe")
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    # Logical grouping, e.g. "performer", "studio", "genre", "keyword"
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Display colour hex (#rrggbb), optional
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)

    media_tags: Mapped[list["MediaTag"]] = relationship(
        back_populates="tag", lazy="noload", cascade="all, delete-orphan"
    )


class MediaTag(Base):
    """Junction table: media_items ↔ tags."""

    __tablename__ = "media_tags"
    __table_args__ = (Index("idx_media_tags_tag", "tag_id"),)

    media_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("media_items.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # 1.0 = manually assigned; 0.0–1.0 = AI confidence score
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    # 'manual' | 'ai' | 'filename'
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    media_item: Mapped["MediaItem"] = relationship(  # noqa: F821
        back_populates="media_tags", lazy="noload"
    )
    tag: Mapped["Tag"] = relationship(back_populates="media_tags", lazy="noload")
