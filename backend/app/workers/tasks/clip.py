"""
Celery tasks for CLIP embedding computation (GPU worker, 'ml' queue).

compute_clip_embedding_task(media_id)
    — opens the item's thumbnail, encodes with CLIP, writes clip_embedding.

backfill_clip_embeddings_task()
    — dispatches compute_clip_embedding_task for all pending items in batches.
"""

from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import select

from app.models.media_item import MediaItem
from app.workers.celery_app import celery_app
from app.workers.db import task_session

log = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    queue="ml",
    max_retries=2,
    default_retry_delay=30,
    name="app.workers.tasks.clip.compute_clip_embedding_task",
)
def compute_clip_embedding_task(self, media_id: str) -> str:
    """Compute and persist the CLIP embedding for a single MediaItem."""
    try:
        return asyncio.run(_compute_embedding(media_id))
    except Exception as exc:
        log.error("clip.task_failed", media_id=media_id, error=str(exc), exc_info=True)
        raise self.retry(exc=exc)


async def _compute_embedding(media_id: str) -> str:
    async with task_session() as session:
        item = await session.get(MediaItem, media_id)
        if item is None:
            log.warning("clip.item_not_found", media_id=media_id)
            return "not_found"

        if not item.thumbnail_path:
            log.debug("clip.no_thumbnail", media_id=media_id)
            item.clip_status = "error"
            return "no_thumbnail"

        item.clip_status = "computing"
        await session.flush()

    try:
        embedding = _encode_thumbnail(item.thumbnail_path)
    except Exception as exc:
        log.error("clip.encode_failed", media_id=media_id, error=str(exc))
        async with task_session() as session:
            it = await session.get(MediaItem, media_id)
            if it:
                it.clip_status = "error"
        return "error"

    async with task_session() as session:
        it = await session.get(MediaItem, media_id)
        if it:
            it.clip_embedding = embedding
            it.clip_status = "done"

    log.info("clip.done", media_id=media_id)
    return "done"


def _encode_thumbnail(thumbnail_path: str) -> list[float]:
    """Open a thumbnail and return a unit-normalised 768-dim CLIP vector."""
    import torch
    from PIL import Image

    from app.ml.clip_model import get_clip_model

    model, preprocess, _ = get_clip_model()
    device = next(model.parameters()).device

    img = Image.open(thumbnail_path).convert("RGB")
    tensor = preprocess(img).unsqueeze(0).to(device)

    with torch.no_grad():
        feat = model.encode_image(tensor)
        feat = feat / feat.norm(dim=-1, keepdim=True)

    return feat[0].cpu().numpy().tolist()


@celery_app.task(
    queue="ml",
    name="app.workers.tasks.clip.backfill_clip_embeddings_task",
)
def backfill_clip_embeddings_task() -> dict:
    """Dispatch compute_clip_embedding_task for all items with clip_status='pending'."""
    return asyncio.run(_backfill())


async def _backfill() -> dict:
    batch_size = 50
    dispatched = 0

    async with task_session() as session:
        result = await session.execute(
            select(MediaItem.id)
            .where(MediaItem.clip_status == "pending")
            .where(MediaItem.thumbnail_path.isnot(None))
        )
        ids = list(result.scalars().all())

    for i in range(0, len(ids), batch_size):
        batch = ids[i: i + batch_size]
        for media_id in batch:
            compute_clip_embedding_task.apply_async(
                kwargs={"media_id": media_id},
                queue="ml",
            )
        dispatched += len(batch)
        log.info("clip.backfill_batch", dispatched=dispatched, total=len(ids))

    log.info("clip.backfill_complete", dispatched=dispatched)
    return {"dispatched": dispatched}
