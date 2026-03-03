"""
Abstract base for media source connectors.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator


@dataclass
class FileEntry:
    """Metadata for a single file discovered by a connector."""

    path: str           # Full path or UNC path to the file
    filename: str       # Basename
    size: int           # File size in bytes
    mtime: datetime     # Last-modified time (UTC)


class AbstractConnector(ABC):
    """Base interface for all media source connectors."""

    @abstractmethod
    async def iter_files(self, scan_config: dict | None = None) -> AsyncIterator[FileEntry]:
        """Yield FileEntry objects for all media files in the source."""
        raise NotImplementedError
        yield  # make this an async generator

    @abstractmethod
    async def stat(self, path: str) -> FileEntry:
        """Return metadata for a single file."""
        raise NotImplementedError

    async def close(self) -> None:
        """Release any underlying connections."""

    async def __aenter__(self) -> "AbstractConnector":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()
