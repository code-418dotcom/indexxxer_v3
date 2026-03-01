"""
Base types for media metadata extraction.

Each extractor takes a filesystem Path and returns a MediaMetadata instance,
or raises ExtractionError if the file cannot be read.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


class ExtractionError(Exception):
    """Raised when a file cannot be read or parsed."""


@dataclass
class MediaMetadata:
    """Normalised output from any extractor."""

    media_type: str                         # 'image' | 'video'
    mime_type: str | None = None

    # Dimensions
    width: int | None = None
    height: int | None = None

    # Video / stream
    duration_seconds: float | None = None
    bitrate: int | None = None              # bits per second
    codec: str | None = None               # e.g. 'h264', 'hevc', 'vp9'
    frame_rate: float | None = None        # fps

    # Raw extra fields (format-specific, stored for future use)
    extra: dict = field(default_factory=dict)


class AbstractExtractor(ABC):
    """Common interface all extractors must implement."""

    @abstractmethod
    def can_handle(self, path: Path) -> bool:
        """Return True if this extractor knows how to process the given path."""

    @abstractmethod
    def extract(self, path: Path) -> MediaMetadata:
        """
        Extract metadata from *path*.

        Raises:
            ExtractionError: if the file cannot be opened or parsed.
        """
