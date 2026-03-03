"""
Local filesystem connector — wraps the existing _iter_media_files logic.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from app.connectors.base import AbstractConnector, FileEntry
from app.extractors.image import IMAGE_EXTENSIONS
from app.extractors.video import VIDEO_EXTENSIONS

_ALL_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


class LocalConnector(AbstractConnector):
    def __init__(self, root_path: str) -> None:
        self._root = Path(root_path)

    async def iter_files(self, scan_config: dict | None = None) -> AsyncIterator[FileEntry]:
        for entry in _iter_media_files_sync(self._root, scan_config):
            yield entry

    async def stat(self, path: str) -> FileEntry:
        p = Path(path)
        s = p.stat()
        return FileEntry(
            path=str(p),
            filename=p.name,
            size=s.st_size,
            mtime=datetime.fromtimestamp(s.st_mtime, tz=timezone.utc),
        )


def _iter_media_files_sync(root: Path, scan_config: dict | None = None):
    """Yield FileEntry for each media file under root (synchronous walk)."""
    cfg = scan_config or {}
    include_exts = frozenset(
        e.lower() for e in cfg.get("include_extensions", list(_ALL_EXTENSIONS))
    )
    skip_hidden: bool = cfg.get("skip_hidden", True)
    max_depth: int | None = cfg.get("max_depth")

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        depth = len(current.relative_to(root).parts)

        if skip_hidden:
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]

        if max_depth is not None and depth > max_depth:
            dirnames.clear()
            continue

        for fname in sorted(filenames):
            if skip_hidden and fname.startswith("."):
                continue
            fpath = current / fname
            if fpath.suffix.lower() not in include_exts:
                continue
            try:
                s = fpath.stat()
                yield FileEntry(
                    path=str(fpath),
                    filename=fname,
                    size=s.st_size,
                    mtime=datetime.fromtimestamp(s.st_mtime, tz=timezone.utc),
                )
            except OSError:
                continue
