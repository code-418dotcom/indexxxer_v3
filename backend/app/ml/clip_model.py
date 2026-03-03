"""
Lazy-loaded CLIP model singleton.

Uses open_clip (ViT-L/14, openai weights) which outputs 768-dim embeddings.
Auto-detects CUDA; falls back to CPU gracefully.

The singleton is created on first call to get_clip_model() and cached in-process
for the lifetime of the worker. Model files are cached by open_clip in
~/.cache/clip (mapped to a Docker volume on the GPU worker).

Usage:
    from app.ml.clip_model import get_clip_model
    model, preprocess, tokenizer = get_clip_model()
    tokens = tokenizer(["a sunset over the ocean"])
    features = model.encode_text(tokens)
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    import open_clip
    import torch

log = structlog.get_logger(__name__)

_lock = threading.Lock()
_model = None
_preprocess = None
_tokenizer = None


def get_clip_model():
    """Return (model, preprocess, tokenizer), loading on first call."""
    global _model, _preprocess, _tokenizer

    if _model is not None:
        return _model, _preprocess, _tokenizer

    with _lock:
        if _model is not None:
            return _model, _preprocess, _tokenizer

        import open_clip
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        log.info("clip_model.loading", device=device, model="ViT-L-14", pretrained="openai")

        model, _, preprocess = open_clip.create_model_and_transforms(
            "ViT-L-14",
            pretrained="openai",
            device=device,
        )
        tokenizer = open_clip.get_tokenizer("ViT-L-14")
        model.eval()

        _model = model
        _preprocess = preprocess
        _tokenizer = tokenizer

        log.info("clip_model.ready", device=device, embedding_dim=768)

    return _model, _preprocess, _tokenizer
