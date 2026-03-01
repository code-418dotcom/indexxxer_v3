"""
Video metadata extractor.

Uses ffprobe (part of ffmpeg) to read container/stream info.
ffprobe must be in PATH — guaranteed by the backend Dockerfile.
"""

from __future__ import annotations

import json
import mimetypes
import subprocess
from fractions import Fraction
from pathlib import Path

import structlog

from app.extractors.base import AbstractExtractor, ExtractionError, MediaMetadata

log = structlog.get_logger(__name__)

VIDEO_EXTENSIONS = frozenset({
    ".mp4", ".m4v",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".webm",
    ".mpg", ".mpeg",
    ".3gp",
    ".ts",
})

_FFPROBE_TIMEOUT = 30  # seconds


def _parse_frame_rate(rate_str: str | None) -> float | None:
    """Convert ffprobe fraction string '30000/1001' → 29.97."""
    if not rate_str or rate_str in ("0/0", "0"):
        return None
    try:
        return float(Fraction(rate_str))
    except (ValueError, ZeroDivisionError):
        return None


class VideoExtractor(AbstractExtractor):
    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() in VIDEO_EXTENSIONS

    def extract(self, path: Path) -> MediaMetadata:
        mime_type = mimetypes.guess_type(str(path))[0] or "video/unknown"

        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "quiet",
                    "-print_format", "json",
                    "-show_format",
                    "-show_streams",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=_FFPROBE_TIMEOUT,
            )
        except subprocess.TimeoutExpired as exc:
            raise ExtractionError(f"ffprobe timed out on {path.name}") from exc
        except FileNotFoundError as exc:
            raise ExtractionError("ffprobe not found in PATH") from exc

        if result.returncode != 0:
            raise ExtractionError(
                f"ffprobe failed on {path.name}: {result.stderr.strip()[:200]}"
            )

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ExtractionError(f"ffprobe returned invalid JSON for {path.name}") from exc

        fmt = data.get("format", {})
        streams = data.get("streams", [])

        # Find the best video stream (highest resolution)
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        if not video_streams:
            raise ExtractionError(f"No video stream found in {path.name}")

        video = max(video_streams, key=lambda s: s.get("width", 0) * s.get("height", 0))

        # Duration: prefer format-level (more accurate for containers)
        duration: float | None = None
        raw_duration = fmt.get("duration") or video.get("duration")
        if raw_duration:
            try:
                duration = float(raw_duration)
            except ValueError:
                pass

        # Bitrate
        bitrate: int | None = None
        raw_bitrate = fmt.get("bit_rate") or video.get("bit_rate")
        if raw_bitrate:
            try:
                bitrate = int(raw_bitrate)
            except ValueError:
                pass

        width = video.get("width")
        height = video.get("height")
        codec = video.get("codec_name")
        fps = _parse_frame_rate(
            video.get("avg_frame_rate") or video.get("r_frame_rate")
        )

        extra: dict = {
            "container": fmt.get("format_name"),
            "nb_streams": fmt.get("nb_streams"),
        }
        if video.get("pix_fmt"):
            extra["pix_fmt"] = video["pix_fmt"]
        if video.get("profile"):
            extra["codec_profile"] = video["profile"]

        return MediaMetadata(
            media_type="video",
            mime_type=mime_type,
            width=int(width) if width else None,
            height=int(height) if height else None,
            duration_seconds=duration,
            bitrate=bitrate,
            codec=codec,
            frame_rate=fps,
            extra=extra,
        )
