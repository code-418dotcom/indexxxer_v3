"""
Whisper large-v3 transcription model via faster-whisper.

Lazy-loaded via the model registry. Uses float16 on GPU, int8 on CPU.
Audio is extracted from video to a temporary WAV file before transcription.

Usage:
    from app.ml.whisper_model import transcribe
    text = transcribe("/media/video.mp4")
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import structlog

from app.ml.registry import registry

log = structlog.get_logger(__name__)

_MODEL_NAME = "whisper"


def _load_whisper():
    from faster_whisper import WhisperModel
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    log.info("whisper.loading", device=device, compute_type=compute_type)
    model = WhisperModel("large-v3", device=device, compute_type=compute_type)
    log.info("whisper.ready", device=device)
    return model


def _extract_audio(video_path: str, wav_path: str) -> None:
    """Extract mono 16kHz WAV from a video file using ffmpeg."""
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            wav_path,
        ],
        capture_output=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg audio extraction failed: {result.stderr.decode()[:500]}"
        )


def transcribe(video_path: str) -> str:
    """
    Extract audio from *video_path* and return the Whisper transcript.

    The caller is responsible for checking duration before dispatching.
    """
    model = registry.get(_MODEL_NAME, _load_whisper)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name

    try:
        log.info("whisper.extracting_audio", path=video_path)
        _extract_audio(video_path, wav_path)

        log.info("whisper.transcribing", path=video_path)
        import math
        segments, info = model.transcribe(
            wav_path,
            beam_size=5,
            vad_filter=True,          # skip silent segments — prevents nan-probability hang
            condition_on_previous_text=False,  # avoid repetition loops
        )
        # language_probability=nan means audio is silent/corrupt — skip iteration
        if math.isnan(info.language_probability):
            log.warning("whisper.nan_probability", path=video_path, lang=info.language)
            return ""
        text = " ".join(seg.text.strip() for seg in segments).strip()
        log.info("whisper.done", path=video_path, chars=len(text))
        return text
    finally:
        Path(wav_path).unlink(missing_ok=True)
