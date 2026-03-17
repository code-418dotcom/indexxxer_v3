"""Torrent download tracking model."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid


class TorrentDownload(Base, TimestampMixin):
    __tablename__ = "torrent_downloads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    torrent_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    performer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("performers.id", ondelete="SET NULL"), nullable=True
    )
    # pending → downloading → moving → completed | error
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    status_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    indexer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    destination_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    performer = relationship("Performer", lazy="joined")
