from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_uuid


class MediaFrameHash(Base):
    """A pHash for a single extracted frame of a video."""

    __tablename__ = "media_frame_hashes"
    __table_args__ = (
        Index("idx_mfh_media", "media_item_id"),
        Index("idx_mfh_phash", "phash"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    media_item_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("media_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    frame_position: Mapped[str] = mapped_column(String(10), nullable=False)
    phash: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    media_item: Mapped["MediaItem"] = relationship(back_populates="frame_hashes", lazy="noload")  # noqa: F821
