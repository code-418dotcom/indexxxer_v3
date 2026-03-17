"""Transmission RPC client wrapper."""

from __future__ import annotations

import structlog
import transmission_rpc

from app.config import settings

log = structlog.get_logger(__name__)

LABEL = "indexxxer"


def get_client() -> transmission_rpc.Client:
    """Create a Transmission RPC client from settings."""
    return transmission_rpc.Client(
        host=settings.transmission_host,
        port=settings.transmission_port,
        username=settings.transmission_username or None,
        password=settings.transmission_password or None,
    )


def add_torrent(
    url: str, download_dir: str | None = None
) -> transmission_rpc.Torrent:
    """Add a torrent with the 'indexxxer' label. Returns the torrent object."""
    client = get_client()
    torrent = client.add_torrent(
        url,
        download_dir=download_dir or settings.torrent_download_dir,
        labels=[LABEL],
    )
    log.info(
        "transmission.added",
        hash=torrent.hashString,
        name=torrent.name,
        download_dir=download_dir,
    )
    return torrent


def add_torrent_base64(
    torrent_b64: str, download_dir: str | None = None
) -> transmission_rpc.Torrent:
    """Add a torrent from base64-encoded .torrent file content."""
    client = get_client()
    torrent = client.add_torrent(
        torrent_b64,
        download_dir=download_dir or settings.torrent_download_dir,
        labels=[LABEL],
    )
    log.info(
        "transmission.added_b64",
        hash=torrent.hashString,
        name=torrent.name,
    )
    return torrent


def get_indexxxer_torrents() -> list[transmission_rpc.Torrent]:
    """Get all torrents with the 'indexxxer' label."""
    client = get_client()
    return [t for t in client.get_torrents() if LABEL in (t.labels or [])]


def remove_torrent(torrent_hash: str, delete_data: bool = False) -> None:
    """Remove a torrent by hash. delete_data=True removes downloaded files."""
    client = get_client()
    client.remove_torrent(torrent_hash, delete_data=delete_data)
    log.info("transmission.removed", hash=torrent_hash, delete_data=delete_data)


def get_torrent(torrent_hash: str) -> transmission_rpc.Torrent | None:
    """Get a single torrent by hash, or None if not found."""
    client = get_client()
    try:
        return client.get_torrent(torrent_hash)
    except Exception:
        return None
