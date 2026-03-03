"""
InsightFace face detection + ArcFace embedding (buffalo_l, 512-dim).

Lazy-loaded via the model registry.
For video items, detection runs on the already-generated thumbnail keyframe.

Usage:
    from app.ml.insightface_model import detect_faces, FaceResult
    faces = detect_faces("/data/thumbnails/ab/abc123.jpg")
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import structlog

from app.ml.registry import registry

log = structlog.get_logger(__name__)

_MODEL_NAME = "insightface"


@dataclass
class FaceResult:
    bbox_x: int
    bbox_y: int
    bbox_w: int
    bbox_h: int
    embedding: np.ndarray  # shape (512,), float32
    confidence: float


def _load_insightface():
    import insightface
    from insightface.app import FaceAnalysis

    log.info("insightface.loading")
    app = FaceAnalysis(name="buffalo_l", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))
    log.info("insightface.ready")
    return app


def detect_faces(image_path: str) -> list[FaceResult]:
    """Detect faces in *image_path* and return bounding boxes + ArcFace embeddings."""
    import cv2

    app = registry.get(_MODEL_NAME, _load_insightface)

    img = cv2.imread(image_path)
    if img is None:
        log.warning("insightface.imread_failed", path=image_path)
        return []

    faces = app.get(img)
    results: list[FaceResult] = []
    for face in faces:
        x1, y1, x2, y2 = face.bbox.astype(int)
        results.append(
            FaceResult(
                bbox_x=int(x1),
                bbox_y=int(y1),
                bbox_w=int(x2 - x1),
                bbox_h=int(y2 - y1),
                embedding=face.embedding.astype(np.float32),
                confidence=float(face.det_score),
            )
        )

    log.debug("insightface.detected", path=image_path, count=len(results))
    return results
