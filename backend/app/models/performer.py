"""
Performer model and MediaPerformer junction table.

Performers are matched to media items via filename/directory name matching,
or linked manually. Profile data can be scraped from freeones.com.
"""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid


class Performer(Base, TimestampMixin):
    """A performer with profile data, optionally scraped from freeones.com."""

    __tablename__ = "performers"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_performer_slug"),
        Index("idx_performer_name", "name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    # Alternate names used for filename matching (e.g. stage names, maiden names)
    aliases: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(255)), nullable=True, default=list
    )

    # ── Profile data (scraped or manual) ─────────────────────────────────────
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    birthdate: Mapped[str | None] = mapped_column(String(50), nullable=True)
    birthplace: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ethnicity: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hair_color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    eye_color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    height: Mapped[str | None] = mapped_column(String(50), nullable=True)
    weight: Mapped[str | None] = mapped_column(String(50), nullable=True)
    measurements: Mapped[str | None] = mapped_column(String(50), nullable=True)
    years_active: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ── Profile image ────────────────────────────────────────────────────────
    # Local path: /data/performers/{id}.jpg
    profile_image_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Scraping metadata ────────────────────────────────────────────────────
    freeones_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    scraped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Denormalized count for fast sorting ──────────────────────────────────
    media_count: Mapped[int] = mapped_column(default=0, nullable=False)

    # ── Relationships ────────────────────────────────────────────────────────
    media_performers: Mapped[list["MediaPerformer"]] = relationship(
        back_populates="performer", lazy="noload", cascade="all, delete-orphan"
    )


class MediaPerformer(Base):
    """Junction table: media_items <-> performers."""

    __tablename__ = "media_performers"
    __table_args__ = (Index("idx_media_performers_performer", "performer_id"),)

    media_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("media_items.id", ondelete="CASCADE"),
        primary_key=True,
    )
    performer_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("performers.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # How the link was established: 'manual', 'filename', 'directory'
    match_source: Mapped[str] = mapped_column(
        String(30), nullable=False, default="manual"
    )
    # Confidence score for auto-matched (1.0 = exact match)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    media_item: Mapped["MediaItem"] = relationship(  # noqa: F821
        back_populates="media_performers", lazy="noload"
    )
    performer: Mapped["Performer"] = relationship(
        back_populates="media_performers", lazy="noload"
    )
