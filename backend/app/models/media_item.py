from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from pgvector.sqlalchemy import Vector as _Vector
    _VECTOR_TYPE = _Vector(768)
except ImportError:
    # pgvector not installed — clip_embedding stored as null-only placeholder
    _VECTOR_TYPE = Text()  # type: ignore[assignment]

from app.models.base import Base, TimestampMixin, new_uuid


class MediaItem(Base, TimestampMixin):
    """
    A single indexed media file (image or video).

    File identity is SHA-256 hash: if a file is moved/renamed, the system
    detects the new path and updates file_path without losing tags.
    """

    __tablename__ = "media_items"
    __table_args__ = (
        UniqueConstraint("source_id", "file_path", name="uq_source_path"),
        Index("idx_media_fts", "search_vector", postgresql_using="gin"),
        Index("idx_media_hash", "file_hash"),
        Index("idx_media_type", "media_type"),
        Index("idx_media_source", "source_id"),
        Index("idx_media_status", "index_status"),
        Index("idx_media_mtime", "file_mtime"),
        Index("idx_media_indexed_at", "indexed_at"),
        Index("idx_media_phash", "perceptual_hash"),
        Index("idx_media_dupgroup", "duplicate_group"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("media_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── File identity ────────────────────────────────────────────────────────
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    # SHA-256 hex digest — populated async; NULL until hashing task completes
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    file_mtime: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Media classification ─────────────────────────────────────────────────
    media_type: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # 'image' | 'video'
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── Dimensions / stream info ─────────────────────────────────────────────
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    bitrate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    codec: Mapped[str | None] = mapped_column(String(50), nullable=True)
    frame_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Derived assets ───────────────────────────────────────────────────────
    # Absolute filesystem path under THUMBNAIL_ROOT
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    # WebM preview strip path (M3)
    preview_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Indexing status ──────────────────────────────────────────────────────
    # pending → extracting → thumbnailing → indexed | error
    index_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending"
    )
    index_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Full-text search ─────────────────────────────────────────────────────
    # Updated by Alembic-managed trigger; also refreshed by tagging worker
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    # ── M2: CLIP semantic embedding ──────────────────────────────────────────
    # 768-dim ViT-L/14 embedding (unit-normalised); NULL until GPU worker runs
    clip_embedding: Mapped[list[float] | None] = mapped_column(
        _VECTOR_TYPE, nullable=True
    )
    # pending | computing | done | error
    clip_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )

    # ── M2: User favourites ──────────────────────────────────────────────────
    is_favourite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── M3: AI enrichment ────────────────────────────────────────────────────
    # BLIP-2 image caption
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    # pending | computing | done | error | skipped
    caption_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    # Whisper transcript (videos ≤ 10 min only)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    # pending | transcribing | done | error | skipped
    transcript_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    # Ollama LLM summary (generated when caption or transcript exists)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # pending | summarising | done | error | skipped
    summary_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )

    # ── Deduplication ──────────────────────────────────────────────────────
    perceptual_hash: Mapped[str | None] = mapped_column(String(16), nullable=True)
    duplicate_group: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # pending | computing | done | error
    dedup_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )

    # ── Relationships ────────────────────────────────────────────────────────
    source: Mapped["MediaSource"] = relationship(  # noqa: F821
        back_populates="media_items", lazy="noload"
    )
    media_tags: Mapped[list["MediaTag"]] = relationship(  # noqa: F821
        back_populates="media_item", lazy="noload", cascade="all, delete-orphan"
    )
    media_performers: Mapped[list["MediaPerformer"]] = relationship(  # noqa: F821
        back_populates="media_item", lazy="noload", cascade="all, delete-orphan"
    )
    frame_hashes: Mapped[list["MediaFrameHash"]] = relationship(  # noqa: F821
        back_populates="media_item", lazy="noload", cascade="all, delete-orphan"
    )
