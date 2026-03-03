"""
Celery tasks for the M3 AI enrichment pipeline.

GPU tasks (queue: ml, concurrency=1 on gpu_worker):
  compute_caption_task    — BLIP-2 image captioning
  compute_transcript_task — Whisper video transcription
  detect_faces_task       — InsightFace face detection + embedding

CPU/HTTP tasks (queue: ai, runs on regular worker):
  compute_summary_task    — Ollama LLM summarisation

Beat tasks:
  cluster_faces_task      — greedy cosine face clustering (every 30 min)
  backfill_ai_task        — dispatch pending AI tasks (every 1 hr)
"""

from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import select, text

from app.models.media_item import MediaItem
from app.workers.celery_app import celery_app
from app.workers.db import task_session

log = structlog.get_logger(__name__)


# ── GPU tasks ──────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    queue="ml",
    max_retries=2,
    default_retry_delay=30,
    name="app.workers.tasks.ai.compute_caption_task",
)
def compute_caption_task(self, media_id: str) -> str:
    """Generate a BLIP-2 caption for an image MediaItem."""
    try:
        return asyncio.run(_compute_caption(media_id))
    except Exception as exc:
        log.error("caption.task_failed", media_id=media_id, error=str(exc), exc_info=True)
        asyncio.run(_set_status(media_id, "caption_status", "error"))
        raise self.retry(exc=exc)


async def _compute_caption(media_id: str) -> str:
    async with task_session() as session:
        item = await session.get(MediaItem, media_id)
        if item is None:
            log.warning("caption.item_not_found", media_id=media_id)
            return "not_found"
        if item.caption_status not in ("pending", "error"):
            return "skip"
        if not item.thumbnail_path:
            item.caption_status = "skipped"
            await session.flush()
            return "no_thumbnail"
        thumbnail_path = item.thumbnail_path
        item.caption_status = "computing"
        await session.flush()

    from app.ml.blip2_model import caption_image
    caption = caption_image(thumbnail_path)

    async with task_session() as session:
        it = await session.get(MediaItem, media_id)
        if it:
            it.caption = caption
            it.caption_status = "done"

    log.info("caption.done", media_id=media_id)

    # Trigger summary if we now have a caption
    compute_summary_task.apply_async(kwargs={"media_id": media_id}, queue="ai")
    return "done"


@celery_app.task(
    bind=True,
    queue="ml",
    max_retries=2,
    default_retry_delay=60,
    time_limit=1200,  # 20 min hard limit
    name="app.workers.tasks.ai.compute_transcript_task",
)
def compute_transcript_task(self, media_id: str) -> str:
    """Whisper-transcribe a video MediaItem (≤10 min duration)."""
    try:
        return asyncio.run(_compute_transcript(media_id))
    except Exception as exc:
        log.error("transcript.task_failed", media_id=media_id, error=str(exc), exc_info=True)
        asyncio.run(_set_status(media_id, "transcript_status", "error"))
        raise self.retry(exc=exc)


async def _compute_transcript(media_id: str) -> str:
    from app.config import settings

    async with task_session() as session:
        item = await session.get(MediaItem, media_id)
        if item is None:
            log.warning("transcript.item_not_found", media_id=media_id)
            return "not_found"
        if item.transcript_status not in ("pending", "error"):
            return "skip"
        if (item.duration_seconds or 0) > settings.whisper_max_duration:
            item.transcript_status = "skipped"
            await session.flush()
            return "too_long"
        if item.media_type != "video":
            item.transcript_status = "skipped"
            await session.flush()
            return "not_video"
        file_path = item.file_path
        item.transcript_status = "transcribing"
        await session.flush()

    from app.ml.whisper_model import transcribe
    transcript = transcribe(file_path)

    async with task_session() as session:
        it = await session.get(MediaItem, media_id)
        if it:
            it.transcript = transcript
            it.transcript_status = "done"

    log.info("transcript.done", media_id=media_id, chars=len(transcript))

    # Trigger summary if we now have a transcript
    compute_summary_task.apply_async(kwargs={"media_id": media_id}, queue="ai")
    return "done"


@celery_app.task(
    bind=True,
    queue="ml",
    max_retries=2,
    default_retry_delay=30,
    name="app.workers.tasks.ai.detect_faces_task",
)
def detect_faces_task(self, media_id: str) -> str:
    """Run InsightFace on the thumbnail and persist detected faces."""
    try:
        return asyncio.run(_detect_faces(media_id))
    except Exception as exc:
        log.error("faces.task_failed", media_id=media_id, error=str(exc), exc_info=True)
        raise self.retry(exc=exc)


async def _detect_faces(media_id: str) -> str:
    from app.models.media_face import MediaFace

    async with task_session() as session:
        item = await session.get(MediaItem, media_id)
        if item is None:
            log.warning("faces.item_not_found", media_id=media_id)
            return "not_found"
        if not item.thumbnail_path:
            return "no_thumbnail"
        thumbnail_path = item.thumbnail_path

        # Skip if faces already detected for this item
        existing = await session.execute(
            select(MediaFace).where(MediaFace.media_id == media_id).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            return "already_done"

    from app.ml.insightface_model import detect_faces
    faces = detect_faces(thumbnail_path)

    if not faces:
        log.debug("faces.none_detected", media_id=media_id)
        return "no_faces"

    async with task_session() as session:
        for face in faces:
            session.add(
                MediaFace(
                    media_id=media_id,
                    bbox_x=face.bbox_x,
                    bbox_y=face.bbox_y,
                    bbox_w=face.bbox_w,
                    bbox_h=face.bbox_h,
                    embedding=face.embedding.tolist(),
                    confidence=face.confidence,
                )
            )

    log.info("faces.done", media_id=media_id, count=len(faces))
    return "done"


# ── CPU/HTTP tasks ─────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    queue="ai",
    max_retries=3,
    default_retry_delay=10,
    name="app.workers.tasks.ai.compute_summary_task",
)
def compute_summary_task(self, media_id: str) -> str:
    """Generate an Ollama summary when caption or transcript exists."""
    try:
        return asyncio.run(_compute_summary(media_id))
    except Exception as exc:
        log.error("summary.task_failed", media_id=media_id, error=str(exc), exc_info=True)
        asyncio.run(_set_status(media_id, "summary_status", "error"))
        raise self.retry(exc=exc)


async def _compute_summary(media_id: str) -> str:
    async with task_session() as session:
        item = await session.get(MediaItem, media_id)
        if item is None:
            return "not_found"
        if item.summary_status not in ("pending", "error"):
            return "skip"
        if not item.caption and not item.transcript:
            return "no_content"

        caption = item.caption
        transcript = item.transcript
        filename = item.filename
        item.summary_status = "summarising"
        await session.flush()

    from app.ml.ollama_client import summarise
    summary = await summarise(caption=caption, transcript=transcript, filename=filename)

    async with task_session() as session:
        it = await session.get(MediaItem, media_id)
        if it:
            it.summary = summary
            it.summary_status = "done"

    log.info("summary.done", media_id=media_id)
    return "done"


# ── Beat task: face clustering ─────────────────────────────────────────────────

@celery_app.task(
    queue="ai",
    name="app.workers.tasks.ai.cluster_faces_task",
)
def cluster_faces_task() -> dict:
    """
    Greedy cosine clustering of face embeddings with cluster_id IS NULL.
    Threshold = 0.6 (cosine similarity). Runs on the regular worker.
    """
    return asyncio.run(_cluster_faces())


async def _cluster_faces() -> dict:
    import numpy as np
    from app.models.media_face import MediaFace

    async with task_session() as session:
        result = await session.execute(
            select(MediaFace.id, MediaFace.embedding).where(
                MediaFace.cluster_id.is_(None),
                MediaFace.embedding.isnot(None),
            )
        )
        rows = result.all()

    if not rows:
        return {"assigned": 0}

    # Load existing cluster embeddings via ORM (pgvector type handled automatically)
    # and compute centroids in Python to avoid unsupported vector→float[] SQL cast.
    async with task_session() as session:
        clustered = await session.execute(
            select(MediaFace.cluster_id, MediaFace.embedding).where(
                MediaFace.cluster_id.isnot(None),
                MediaFace.embedding.isnot(None),
            )
        )
        clustered_rows = clustered.all()

    from collections import defaultdict
    cluster_emb_lists: dict[int, list[np.ndarray]] = defaultdict(list)
    for cid, emb in clustered_rows:
        if emb is not None:
            cluster_emb_lists[cid].append(np.array(emb, dtype=np.float32))

    centroids: list[tuple[int, np.ndarray]] = []
    for cid, embs in cluster_emb_lists.items():
        centroid = np.mean(embs, axis=0)
        norm = np.linalg.norm(centroid)
        if norm > 0:
            centroid = centroid / norm
        centroids.append((cid, centroid))

    next_cluster_id = max((c for c, _ in centroids), default=-1) + 1

    assignments: list[tuple[str, int]] = []

    for face_id, embedding in rows:
        if embedding is None:
            continue
        emb = np.array(embedding, dtype=np.float32)
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm

        best_cluster: int | None = None
        best_sim = 0.0

        for cluster_id, centroid in centroids:
            sim = float(np.dot(emb, centroid))
            if sim > best_sim:
                best_sim = sim
                best_cluster = cluster_id

        if best_cluster is None or best_sim < 0.28:
            # Start a new cluster
            best_cluster = next_cluster_id
            next_cluster_id += 1
            centroids.append((best_cluster, emb.copy()))
        else:
            # Update centroid (running mean approximation)
            idx = next(i for i, (c, _) in enumerate(centroids) if c == best_cluster)
            old = centroids[idx][1]
            centroids[idx] = (best_cluster, (old + emb) / 2.0)

        assignments.append((face_id, best_cluster))

    # Bulk update
    if assignments:
        async with task_session() as session:
            for face_id, cluster_id in assignments:
                await session.execute(
                    text("UPDATE media_faces SET cluster_id = :c WHERE id = :id"),
                    {"c": cluster_id, "id": face_id},
                )

    log.info("cluster_faces.done", assigned=len(assignments))
    return {"assigned": len(assignments)}


# ── Beat task: AI backfill ─────────────────────────────────────────────────────

@celery_app.task(
    queue="ai",
    name="app.workers.tasks.ai.backfill_ai_task",
)
def backfill_ai_task() -> dict:
    """Dispatch AI tasks for all items that still have pending status."""
    return asyncio.run(_backfill_ai())


async def _backfill_ai() -> dict:
    from app.config import settings

    async with task_session() as session:
        # Images pending caption
        img_caption = await session.execute(
            select(MediaItem.id)
            .where(MediaItem.media_type == "image")
            .where(MediaItem.caption_status == "pending")
            .where(MediaItem.thumbnail_path.isnot(None))
        )
        caption_ids = list(img_caption.scalars())

        # Videos pending transcript (≤ max duration)
        vid_trans = await session.execute(
            select(MediaItem.id)
            .where(MediaItem.media_type == "video")
            .where(MediaItem.transcript_status == "pending")
            .where(MediaItem.duration_seconds <= settings.whisper_max_duration)
        )
        transcript_ids = list(vid_trans.scalars())

        # Items with thumbnail but no face rows yet
        face_pending = await session.execute(
            text(
                """
                SELECT mi.id FROM media_items mi
                WHERE mi.thumbnail_path IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM media_faces mf WHERE mf.media_id = mi.id
                )
                """
            )
        )
        face_ids = [str(row[0]) for row in face_pending]

    for mid in caption_ids:
        compute_caption_task.apply_async(kwargs={"media_id": mid}, queue="ml")
    for mid in transcript_ids:
        compute_transcript_task.apply_async(kwargs={"media_id": mid}, queue="ml")
    for mid in face_ids:
        detect_faces_task.apply_async(kwargs={"media_id": mid}, queue="ml")

    log.info(
        "backfill_ai.dispatched",
        captions=len(caption_ids),
        transcripts=len(transcript_ids),
        faces=len(face_ids),
    )
    return {
        "captions": len(caption_ids),
        "transcripts": len(transcript_ids),
        "faces": len(face_ids),
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _set_status(media_id: str, field: str, value: str) -> None:
    async with task_session() as session:
        await session.execute(
            text(f"UPDATE media_items SET {field} = :v WHERE id = :id"),
            {"v": value, "id": media_id},
        )
