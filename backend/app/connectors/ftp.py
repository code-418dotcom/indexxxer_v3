"""
FTP connector using aioftp (native async).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import AsyncIterator

import structlog

from app.connectors.base import AbstractConnector, FileEntry
from app.extractors.image import IMAGE_EXTENSIONS
from app.extractors.video import VIDEO_EXTENSIONS

log = structlog.get_logger(__name__)

_ALL_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


class FTPConnector(AbstractConnector):
    def __init__(
        self,
        host: str,
        port: int = 21,
        base_path: str = "/",
        username: str = "anonymous",
        password: str = "",
    ) -> None:
        self._host = host
        self._port = port
        self._base_path = base_path
        self._username = username
        self._password = password

    async def iter_files(self, scan_config: dict | None = None) -> AsyncIterator[FileEntry]:
        import aioftp  # type: ignore

        cfg = scan_config or {}
        include_exts = frozenset(
            e.lower() for e in cfg.get("include_extensions", list(_ALL_EXTENSIONS))
        )
        skip_hidden: bool = cfg.get("skip_hidden", True)

        async with aioftp.Client.context(
            self._host,
            port=self._port,
            user=self._username,
            password=self._password,
        ) as client:
            async for path, info in client.list(self._base_path, recursive=True):
                if info["type"] != "file":
                    continue
                fname = str(path).split("/")[-1]
                if skip_hidden and fname.startswith("."):
                    continue
                ext = os.path.splitext(fname)[1].lower()
                if ext not in include_exts:
                    continue
                try:
                    size = int(info.get("size", 0))
                    # aioftp provides modify time as a string; parse it
                    mtime_str = info.get("modify", "")
                    if mtime_str:
                        mtime = datetime.strptime(mtime_str, "%Y%m%d%H%M%S").replace(
                            tzinfo=timezone.utc
                        )
                    else:
                        mtime = datetime.now(timezone.utc)
                    yield FileEntry(
                        path=str(path),
                        filename=fname,
                        size=size,
                        mtime=mtime,
                    )
                except Exception as exc:
                    log.warning("ftp.entry_error", path=str(path), error=str(exc))

    async def stat(self, path: str) -> FileEntry:
        import aioftp  # type: ignore

        async with aioftp.Client.context(
            self._host,
            port=self._port,
            user=self._username,
            password=self._password,
        ) as client:
            info = await client.stat(path)
            size = int(info.get("size", 0))
            mtime_str = info.get("modify", "")
            if mtime_str:
                mtime = datetime.strptime(mtime_str, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
            else:
                mtime = datetime.now(timezone.utc)
            return FileEntry(
                path=path,
                filename=path.split("/")[-1],
                size=size,
                mtime=mtime,
            )
