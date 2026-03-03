from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from pgvector.sqlalchemy import Vector as _Vector
    _FACE_VECTOR_TYPE = _Vector(512)
except ImportError:
    from sqlalchemy import Text
    _FACE_VECTOR_TYPE = Text()  # type: ignore[assignment]

from app.models.base import Base, new_uuid


class MediaFace(Base):
    """A single detected face within a MediaItem's thumbnail."""

    __tablename__ = "media_faces"
    __table_args__ = (
        Index("idx_faces_media", "media_id"),
        Index("idx_faces_cluster", "cluster_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    media_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("media_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    cluster_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Bounding box (pixels)
    bbox_x: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_y: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_w: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_h: Mapped[int] = mapped_column(Integer, nullable=False)

    # ArcFace 512-dim embedding (unit-normalised)
    embedding: Mapped[list[float] | None] = mapped_column(_FACE_VECTOR_TYPE, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ────────────────────────────────────────────────────────
    media_item: Mapped["MediaItem"] = relationship(  # noqa: F821
        back_populates="faces", lazy="noload"
    )
