"""
Local filesystem storage helpers for M1.

Thumbnail serving: local disk under THUMBNAIL_ROOT.
M4 swap point: replace these with MinIO/S3 presigned URL logic.
"""

from pathlib import Path

from app.config import settings
from app.models.media_item import MediaItem


def get_thumbnail_path(item: MediaItem) -> Path | None:
    """Return the on-disk Path of the thumbnail if the file exists, else None."""
    if not item.thumbnail_path:
        return None
    p = Path(item.thumbnail_path)
    return p if p.exists() else None


def make_thumbnail_url(item_id: str) -> str:
    """Construct the API URL clients use to fetch a thumbnail."""
    return f"{settings.api_v1_prefix}/media/{item_id}/thumbnail"


def get_performer_image_dir() -> Path:
    """Return the directory for performer profile images."""
    return Path(settings.thumbnail_root).parent / "performers"


def get_performer_image_path(performer_id: str) -> Path:
    """Return the on-disk Path for a performer's profile image."""
    return get_performer_image_dir() / f"{performer_id}.jpg"


def make_performer_image_url(performer_id: str) -> str:
    """Construct the API URL clients use to fetch a performer image."""
    return f"{settings.api_v1_prefix}/performers/{performer_id}/image"
