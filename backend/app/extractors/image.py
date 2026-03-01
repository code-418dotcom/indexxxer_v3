"""
Image metadata extractor.

Uses Pillow for dimensions and basic format info, exifread for richer EXIF data.
Handles EXIF orientation transparently (width/height are always post-rotation).
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

import exifread
import structlog
from PIL import Image, ImageOps, UnidentifiedImageError

from app.extractors.base import AbstractExtractor, ExtractionError, MediaMetadata

log = structlog.get_logger(__name__)

# Extensions this extractor handles
IMAGE_EXTENSIONS = frozenset({
    ".jpg", ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".bmp",
    ".tiff", ".tif",
    ".avif",
    ".heic", ".heif",
})


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    try:
        return numerator / denominator if denominator else None
    except (TypeError, ZeroDivisionError):
        return None


class ImageExtractor(AbstractExtractor):
    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() in IMAGE_EXTENSIONS

    def extract(self, path: Path) -> MediaMetadata:
        mime_type = mimetypes.guess_type(str(path))[0] or "image/unknown"

        try:
            with Image.open(path) as img:
                # Apply EXIF orientation so width/height are visually correct
                img = ImageOps.exif_transpose(img)
                width, height = img.size
                extra: dict = {"format": img.format, "mode": img.mode}
        except UnidentifiedImageError as exc:
            raise ExtractionError(f"Unrecognised image format: {path.name}") from exc
        except Exception as exc:
            raise ExtractionError(f"Could not open image {path.name}: {exc}") from exc

        # Supplement with EXIF data where available
        try:
            with open(path, "rb") as fh:
                tags = exifread.process_file(fh, stop_tag="GPS GPSLatitude", details=False)
            if tags:
                # GPS (stored for future use)
                lat = tags.get("GPS GPSLatitude")
                lon = tags.get("GPS GPSLongitude")
                if lat and lon:
                    extra["gps_raw"] = {"lat": str(lat), "lon": str(lon)}
                # Camera
                make = tags.get("Image Make")
                model = tags.get("Image Model")
                if make:
                    extra["camera_make"] = str(make)
                if model:
                    extra["camera_model"] = str(model)
                # Capture date
                date_tag = tags.get("EXIF DateTimeOriginal") or tags.get("Image DateTime")
                if date_tag:
                    extra["capture_date"] = str(date_tag)
        except Exception as exc:
            # EXIF read is best-effort; never fail the extraction
            log.debug("exif.read_failed", path=str(path), error=str(exc))

        return MediaMetadata(
            media_type="image",
            mime_type=mime_type,
            width=width,
            height=height,
            extra=extra,
        )
