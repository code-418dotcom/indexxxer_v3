"""
Deduplication service — pure functions for two-phase dedup.

Phase 1 (pre-filter): SQL-level bucketing by duration/resolution.
Phase 2 (confirm):    Multi-frame pHash comparison for videos,
                      single pHash for images, content hash for galleries.
"""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
from pathlib import Path

import imagehash
import structlog
from PIL import Image

log = structlog.get_logger(__name__)

HAMMING_THRESHOLD = 8
VIDEO_FRAME_POSITIONS = [0.10, 0.25, 0.50, 0.75]  # skip intro, sample 4 frames
DURATION_TOLERANCE = 0.02  # ±2%
MIN_FRAME_MATCHES = 3  # out of 4 frames must match to declare duplicate


def compute_phash(path: str | Path) -> str:
    """Compute 64-bit perceptual hash on an image file. Returns hex string."""
    img = Image.open(path)
    h = imagehash.phash(img)
    return str(h)


def hamming_distance(h1: str, h2: str) -> int:
    """Hamming distance between two hex hash strings."""
    return bin(int(h1, 16) ^ int(h2, 16)).count("1")


def extract_video_frames(
    file_path: str, duration: float
) -> list[tuple[str, Path]]:
    """
    Extract 4 frames from a video at fixed percentages of duration.
    Returns list of (position_label, temp_file_path).
    Caller must clean up the temp files.
    """
    frames: list[tuple[str, Path]] = []
    tmpdir = Path(tempfile.mkdtemp(prefix="dedup_"))

    for pct in VIDEO_FRAME_POSITIONS:
        seek = duration * pct
        label = str(int(pct * 100))
        out_path = tmpdir / f"frame_{label}.jpg"

        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{seek:.2f}",
            "-i", file_path,
            "-vframes", "1",
            "-q:v", "2",
            "-f", "image2",
            str(out_path),
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, timeout=30,
            )
            if result.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
                frames.append((label, out_path))
            else:
                log.debug("dedup.frame_extract_failed", seek=seek, path=file_path)
        except (subprocess.TimeoutExpired, OSError) as exc:
            log.warning("dedup.ffmpeg_error", seek=seek, error=str(exc))

    return frames


def compare_frame_hashes(
    new_hashes: dict[str, str],
    candidate_hashes: dict[str, str],
    threshold: int = HAMMING_THRESHOLD,
) -> tuple[bool, int]:
    """
    Compare two sets of frame hashes by matching positions.
    Returns (is_duplicate, matching_frame_count).
    """
    matches = 0
    compared = 0
    for pos, h1 in new_hashes.items():
        h2 = candidate_hashes.get(pos)
        if h2 is None:
            continue
        compared += 1
        if hamming_distance(h1, h2) <= threshold:
            matches += 1

    is_dup = compared >= MIN_FRAME_MATCHES and matches >= MIN_FRAME_MATCHES
    return is_dup, matches


def compute_gallery_content_hash(phashes: list[str]) -> str:
    """SHA256 of sorted concatenated pHash strings → stable gallery fingerprint."""
    combined = "".join(sorted(phashes))
    return hashlib.sha256(combined.encode()).hexdigest()


def duration_range(duration: float) -> tuple[float, float]:
    """Return (low, high) bounds for ±2% duration tolerance."""
    margin = duration * DURATION_TOLERANCE
    return duration - margin, duration + margin
