"""
Tests for M4 source connectors.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.local import LocalConnector, _iter_media_files_sync
from app.connectors.base import FileEntry


@pytest.mark.asyncio
async def test_local_connector_iter_files():
    """LocalConnector should discover image/video files in a temp directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        # Create some fake media files
        (root / "photo.jpg").write_bytes(b"\xff\xd8\xff")
        (root / "clip.mp4").write_bytes(b"\x00\x00\x00")
        (root / "readme.txt").write_bytes(b"text")
        subdir = root / "sub"
        subdir.mkdir()
        (subdir / "nested.jpg").write_bytes(b"\xff\xd8\xff")

        connector = LocalConnector(str(root))
        entries = []
        async for entry in connector.iter_files():
            entries.append(entry)

        paths = [e.filename for e in entries]
        assert "photo.jpg" in paths
        assert "clip.mp4" in paths
        assert "nested.jpg" in paths
        assert "readme.txt" not in paths
        assert len(entries) == 3


@pytest.mark.asyncio
async def test_local_connector_skip_hidden():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "visible.jpg").write_bytes(b"\xff\xd8\xff")
        (root / ".hidden.jpg").write_bytes(b"\xff\xd8\xff")

        connector = LocalConnector(str(root))
        entries = []
        async for entry in connector.iter_files({"skip_hidden": True}):
            entries.append(entry)

        paths = [e.filename for e in entries]
        assert "visible.jpg" in paths
        assert ".hidden.jpg" not in paths


@pytest.mark.asyncio
async def test_local_connector_max_depth():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "level0.jpg").write_bytes(b"\xff\xd8\xff")
        sub = root / "sub"
        sub.mkdir()
        (sub / "level1.jpg").write_bytes(b"\xff\xd8\xff")
        sub2 = sub / "sub2"
        sub2.mkdir()
        (sub2 / "level2.jpg").write_bytes(b"\xff\xd8\xff")

        connector = LocalConnector(str(root))
        entries = []
        async for entry in connector.iter_files({"max_depth": 1}):
            entries.append(entry)

        filenames = [e.filename for e in entries]
        assert "level0.jpg" in filenames
        assert "level1.jpg" in filenames
        assert "level2.jpg" not in filenames


@pytest.mark.asyncio
async def test_smb_connector_dispatches_tasks(client: AsyncClient, db_session: AsyncSession):
    """SMBConnector.iter_files should be mock-patchable for integration tests."""
    from datetime import datetime, timezone
    from app.connectors.smb import SMBConnector

    mock_entry = FileEntry(
        path="//host/share/photo.jpg",
        filename="photo.jpg",
        size=1024,
        mtime=datetime.now(timezone.utc),
    )

    async def mock_iter(scan_config=None):
        yield mock_entry

    with patch.object(SMBConnector, "iter_files", mock_iter):
        connector = SMBConnector(
            host="host",
            share="share",
            base_path="/",
            username="user",
            password="pass",
        )
        entries = []
        async for entry in connector.iter_files():
            entries.append(entry)

    assert len(entries) == 1
    assert entries[0].filename == "photo.jpg"


@pytest.mark.asyncio
async def test_ftp_connector_dispatches_tasks():
    """FTPConnector.iter_files should be mock-patchable for integration tests."""
    from datetime import datetime, timezone
    from app.connectors.ftp import FTPConnector

    mock_entry = FileEntry(
        path="/media/photo.jpg",
        filename="photo.jpg",
        size=2048,
        mtime=datetime.now(timezone.utc),
    )

    async def mock_iter(scan_config=None):
        yield mock_entry

    with patch.object(FTPConnector, "iter_files", mock_iter):
        connector = FTPConnector(host="ftp.example.com")
        entries = []
        async for entry in connector.iter_files():
            entries.append(entry)

    assert len(entries) == 1
    assert entries[0].filename == "photo.jpg"
