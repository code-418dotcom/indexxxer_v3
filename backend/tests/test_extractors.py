"""
Unit tests for media extractors and hashing helper.

These tests run without a database or Docker — they only touch the filesystem
and (for video) mock subprocess calls.
"""

from __future__ import annotations

import io
import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.extractors.base import ExtractionError
from app.extractors.image import ImageExtractor
from app.extractors.video import VideoExtractor
from app.workers.tasks.hashing import partial_sha256
from app.workers.tasks.thumbnail import thumbnail_path_for


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_jpeg(tmp_path: Path) -> Path:
    """Write a minimal 10×10 RGB JPEG to a temp file."""
    img = Image.new("RGB", (10, 10), color=(100, 149, 237))
    path = tmp_path / "test.jpg"
    img.save(path, format="JPEG")
    return path


@pytest.fixture
def tmp_png(tmp_path: Path) -> Path:
    img = Image.new("RGBA", (20, 15), color=(255, 0, 0, 128))
    path = tmp_path / "test.png"
    img.save(path, format="PNG")
    return path


@pytest.fixture
def fake_video(tmp_path: Path) -> Path:
    """An empty file with a .mp4 extension (ffprobe is mocked, content ignored)."""
    path = tmp_path / "test.mp4"
    path.write_bytes(b"\x00" * 128)
    return path


_FFPROBE_RESPONSE = {
    "format": {
        "filename": "test.mp4",
        "nb_streams": 1,
        "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
        "duration": "12.345",
        "bit_rate": "2000000",
    },
    "streams": [
        {
            "codec_type": "video",
            "codec_name": "h264",
            "width": 1920,
            "height": 1080,
            "avg_frame_rate": "30000/1001",
            "bit_rate": "1800000",
            "pix_fmt": "yuv420p",
        }
    ],
}


# ── ImageExtractor ─────────────────────────────────────────────────────────────

class TestImageExtractor:
    ext = ImageExtractor()

    def test_can_handle_jpg(self, tmp_jpeg):
        assert self.ext.can_handle(tmp_jpeg) is True

    def test_can_handle_png(self, tmp_png):
        assert self.ext.can_handle(tmp_png) is True

    def test_cannot_handle_video(self, fake_video):
        assert self.ext.can_handle(fake_video) is False

    def test_cannot_handle_unknown_ext(self, tmp_path):
        assert self.ext.can_handle(tmp_path / "file.xyz") is False

    def test_extract_jpeg_returns_correct_media_type(self, tmp_jpeg):
        meta = self.ext.extract(tmp_jpeg)
        assert meta.media_type == "image"

    def test_extract_jpeg_dimensions(self, tmp_jpeg):
        meta = self.ext.extract(tmp_jpeg)
        assert meta.width == 10
        assert meta.height == 10

    def test_extract_png_rgba_converts(self, tmp_png):
        # PNG with RGBA mode — extractor should still succeed
        meta = self.ext.extract(tmp_png)
        assert meta.media_type == "image"
        assert meta.width == 20
        assert meta.height == 15

    def test_extract_mime_type_jpeg(self, tmp_jpeg):
        meta = self.ext.extract(tmp_jpeg)
        assert meta.mime_type is not None
        assert "jpeg" in meta.mime_type or "jpg" in meta.mime_type

    def test_extract_corrupt_raises(self, tmp_path):
        bad = tmp_path / "corrupt.jpg"
        bad.write_bytes(b"not an image at all")
        with pytest.raises(ExtractionError):
            self.ext.extract(bad)


# ── VideoExtractor ─────────────────────────────────────────────────────────────

class TestVideoExtractor:
    ext = VideoExtractor()

    def test_can_handle_mp4(self, fake_video):
        assert self.ext.can_handle(fake_video) is True

    def test_cannot_handle_jpeg(self, tmp_jpeg):
        assert self.ext.can_handle(tmp_jpeg) is False

    def test_extract_parses_ffprobe_output(self, fake_video):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(_FFPROBE_RESPONSE)
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            meta = self.ext.extract(fake_video)

        assert meta.media_type == "video"
        assert meta.width == 1920
        assert meta.height == 1080
        assert meta.codec == "h264"
        assert meta.duration_seconds == pytest.approx(12.345)
        assert meta.frame_rate == pytest.approx(29.97, rel=0.01)

    def test_extract_ffprobe_failure_raises(self, fake_video):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "invalid data found"

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(ExtractionError):
                self.ext.extract(fake_video)

    def test_extract_ffprobe_timeout_raises(self, fake_video):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ffprobe", 30)):
            with pytest.raises(ExtractionError, match="timed out"):
                self.ext.extract(fake_video)

    def test_extract_no_video_stream_raises(self, fake_video):
        audio_only = {
            "format": {"duration": "60.0", "bit_rate": "128000"},
            "streams": [{"codec_type": "audio", "codec_name": "aac"}],
        }
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(audio_only)
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(ExtractionError, match="No video stream"):
                self.ext.extract(fake_video)


# ── Hashing helper ─────────────────────────────────────────────────────────────

class TestPartialSha256:
    def test_returns_64_char_hex(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_bytes(b"hello world")
        digest = partial_sha256(f)
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_same_content_same_digest(self, tmp_path):
        f1 = tmp_path / "a.bin"
        f2 = tmp_path / "b.bin"
        f1.write_bytes(b"abc" * 1000)
        f2.write_bytes(b"abc" * 1000)
        assert partial_sha256(f1) == partial_sha256(f2)

    def test_different_content_different_digest(self, tmp_path):
        f1 = tmp_path / "a.bin"
        f2 = tmp_path / "b.bin"
        f1.write_bytes(b"aaa")
        f2.write_bytes(b"bbb")
        assert partial_sha256(f1) != partial_sha256(f2)

    def test_same_content_different_size_different_digest(self, tmp_path):
        # Two files with same first chunk but different total sizes → different hash
        f1 = tmp_path / "a.bin"
        f2 = tmp_path / "b.bin"
        chunk = b"x" * 512
        f1.write_bytes(chunk)
        f2.write_bytes(chunk + b"y")
        assert partial_sha256(f1) != partial_sha256(f2)


# ── Thumbnail path helper ──────────────────────────────────────────────────────

class TestThumbnailPath:
    def test_shard_uses_first_two_chars(self):
        item_id = "abcd1234-5678-90ef-abcd-1234567890ef"
        from app.config import settings
        expected = settings.thumbnail_root_path / "ab" / f"{item_id}.jpg"
        assert thumbnail_path_for(item_id) == expected

    def test_different_ids_different_shards(self):
        p1 = thumbnail_path_for("aa000000-0000-0000-0000-000000000000")
        p2 = thumbnail_path_for("bb000000-0000-0000-0000-000000000000")
        assert p1.parent != p2.parent
