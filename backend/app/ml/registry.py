"""
Thread-safe LRU model registry for the GPU worker.

All ML models (CLIP, BLIP-2, Whisper, InsightFace) are loaded lazily and
cached in-process. The RTX 4000 ADA has 20 GB VRAM; all M3 models together
use ~12 GB so eviction is rare but available under memory pressure.

Usage:
    from app.ml.registry import registry

    model = registry.get("blip2", lambda: load_blip2())
    registry.evict("blip2")   # free VRAM
    registry.clear()          # evict all
"""

from __future__ import annotations

import threading
from typing import Any, Callable

import structlog

log = structlog.get_logger(__name__)


class ModelRegistry:
    def __init__(self) -> None:
        self._models: dict[str, Any] = {}
        self._lock = threading.Lock()

    def get(self, name: str, loader_fn: Callable[[], Any]) -> Any:
        """Return the cached model, loading it on first call."""
        if name in self._models:
            return self._models[name]
        with self._lock:
            if name in self._models:
                return self._models[name]
            log.info("registry.loading", model=name)
            self._models[name] = loader_fn()
            log.info("registry.loaded", model=name)
        return self._models[name]

    def evict(self, name: str) -> None:
        """Remove a model and clear the CUDA memory cache."""
        with self._lock:
            if name not in self._models:
                return
            del self._models[name]
            log.info("registry.evicted", model=name)
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    def clear(self) -> None:
        """Evict all cached models."""
        with self._lock:
            names = list(self._models.keys())
            self._models.clear()
        log.info("registry.cleared", evicted=names)
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass


# Process-level singleton — lives for the GPU worker process lifetime
registry = ModelRegistry()
