"""Business logic for torrent download tracking."""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import settings
from app.models.torrent_download import TorrentDownload

log = structlog.get_logger(__name__)


async def create_download(
    session: AsyncSession,
    *,
    torrent_hash: str,
    title: str,
    size: int | None,
    performer_id: str,
    source_url: str,
    indexer: str | None,
) -> TorrentDownload:
    dl = TorrentDownload(
        torrent_hash=torrent_hash,
        title=title,
        size=size,
        performer_id=performer_id,
        source_url=source_url,
        indexer=indexer,
        status="pending",
        progress=0.0,
    )
    session.add(dl)
    await session.flush()
    await session.refresh(dl, ["performer"])
    return dl


async def get_by_hash(
    session: AsyncSession, torrent_hash: str
) -> TorrentDownload | None:
    stmt = (
        select(TorrentDownload)
        .options(joinedload(TorrentDownload.performer))
        .where(TorrentDownload.torrent_hash == torrent_hash)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_download(
    session: AsyncSession, download_id: str
) -> TorrentDownload | None:
    stmt = (
        select(TorrentDownload)
        .options(joinedload(TorrentDownload.performer))
        .where(TorrentDownload.id == download_id)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_downloads(
    session: AsyncSession,
    statuses: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[TorrentDownload]:
    stmt = (
        select(TorrentDownload)
        .options(joinedload(TorrentDownload.performer))
        .order_by(TorrentDownload.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if statuses:
        stmt = stmt.where(TorrentDownload.status.in_(statuses))
    result = await session.execute(stmt)
    return list(result.scalars().unique().all())


def _sanitize_name(name: str) -> str:
    """Make a performer name filesystem-safe."""
    return name.replace("/", "_").replace("\\", "_").replace("..", "_").strip()


def move_completed_files(
    torrent_name: str,
    download_dir: str,
    performer_name: str,
) -> tuple[str, list[str]]:
    """
    Move downloaded torrent files to the performer's directory.

    Returns (destination_dir, list_of_moved_file_paths).
    """
    safe_name = _sanitize_name(performer_name)
    dest_root = Path(settings.torrent_destination_root) / safe_name
    dest_root.mkdir(parents=True, exist_ok=True)

    source = Path(download_dir) / torrent_name
    moved_files: list[str] = []

    if source.is_dir():
        # Multi-file torrent: move contents into performer dir
        for item in source.iterdir():
            dest = dest_root / item.name
            shutil.move(str(item), str(dest))
            if dest.is_file():
                moved_files.append(str(dest))
            elif dest.is_dir():
                for f in dest.rglob("*"):
                    if f.is_file():
                        moved_files.append(str(f))
        # Remove now-empty source directory
        try:
            source.rmdir()
        except OSError:
            pass
    elif source.is_file():
        dest = dest_root / source.name
        shutil.move(str(source), str(dest))
        moved_files.append(str(dest))
    else:
        raise FileNotFoundError(f"Torrent files not found at {source}")

    log.info(
        "torrent.moved",
        source=str(source),
        dest=str(dest_root),
        file_count=len(moved_files),
    )
    return str(dest_root), moved_files
