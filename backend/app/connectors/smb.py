"""
SMB (Windows file share) connector using smbprotocol.
smbprotocol is synchronous — all operations run in a thread executor.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import AsyncIterator

import structlog

from app.connectors.base import AbstractConnector, FileEntry
from app.extractors.image import IMAGE_EXTENSIONS
from app.extractors.video import VIDEO_EXTENSIONS

log = structlog.get_logger(__name__)

_ALL_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


def _unc(host: str, share: str, path: str) -> str:
    """Build a UNC-style path string: //host/share/path"""
    return f"//{host}/{share}/{path.lstrip('/')}"


class SMBConnector(AbstractConnector):
    def __init__(
        self,
        host: str,
        share: str,
        base_path: str,
        username: str = "",
        password: str = "",
        domain: str = "",
        port: int = 445,
    ) -> None:
        self._host = host
        self._share = share
        self._base_path = base_path.lstrip("/")
        self._username = username
        self._password = password
        self._domain = domain
        self._port = port

    def _list_files_sync(self, scan_config: dict | None = None) -> list[FileEntry]:
        """Walk the SMB share synchronously and return a list of FileEntry."""
        import smbclient  # type: ignore

        cfg = scan_config or {}
        include_exts = frozenset(
            e.lower() for e in cfg.get("include_extensions", list(_ALL_EXTENSIONS))
        )
        skip_hidden: bool = cfg.get("skip_hidden", True)

        smbclient.register_session(
            self._host,
            username=self._username,
            password=self._password,
            port=self._port,
        )

        root_unc = rf"\\{self._host}\{self._share}\{self._base_path}"
        results: list[FileEntry] = []

        for dirpath, dirnames, filenames in smbclient.walk(root_unc):
            if skip_hidden:
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for fname in sorted(filenames):
                if skip_hidden and fname.startswith("."):
                    continue
                ext = os.path.splitext(fname)[1].lower()
                if ext not in include_exts:
                    continue
                fpath = rf"{dirpath}\{fname}"
                try:
                    stat = smbclient.stat(fpath)
                    mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                    results.append(
                        FileEntry(
                            path=fpath,
                            filename=fname,
                            size=stat.st_size,
                            mtime=mtime,
                        )
                    )
                except Exception as exc:
                    log.warning("smb.stat_failed", path=fpath, error=str(exc))

        return results

    async def iter_files(self, scan_config: dict | None = None) -> AsyncIterator[FileEntry]:
        loop = asyncio.get_event_loop()
        entries = await loop.run_in_executor(None, self._list_files_sync, scan_config)
        for entry in entries:
            yield entry

    async def stat(self, path: str) -> FileEntry:
        import smbclient  # type: ignore

        loop = asyncio.get_event_loop()

        def _stat_sync():
            s = smbclient.stat(path)
            return FileEntry(
                path=path,
                filename=os.path.basename(path),
                size=s.st_size,
                mtime=datetime.fromtimestamp(s.st_mtime, tz=timezone.utc),
            )

        return await loop.run_in_executor(None, _stat_sync)
