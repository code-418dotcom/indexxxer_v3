"""
Face detection and cluster endpoints (M3).

GET  /faces/stats                — aggregate face/cluster counts
POST /faces/cluster              — trigger cluster_faces_task on demand
GET  /faces/clusters             — list all clusters with member count + representative image
GET  /faces/clusters/{cluster_id} — paginated media IDs in a specific cluster
GET  /media/{media_id}/faces     — all detected faces for a specific media item
"""

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import Auth
from app.database import get_db
from app.schemas.face import FaceClusterMediaResponse, FaceClusterSchema, FaceSchema, FaceStatsSchema
from app.services import face_service

router = APIRouter(tags=["faces"])


@router.get("/faces/stats", response_model=FaceStatsSchema)
async def get_face_stats(
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
) -> FaceStatsSchema:
    """Return aggregate face detection and clustering counts."""
    return await face_service.get_stats(db)


@router.post("/faces/cluster", status_code=202)
async def trigger_clustering(
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Enqueue cluster_faces_task immediately (normally runs every 30 min)."""
    stats = await face_service.get_stats(db)
    from app.workers.tasks.ai import cluster_faces_task
    task = cluster_faces_task.apply_async(queue="ai")
    return {"status": "queued", "task_id": task.id, "unclustered_before": stats.unclustered}


@router.post("/faces/backfill", status_code=202)
async def trigger_backfill(
    _: None = Auth,
) -> dict:
    """Enqueue backfill_ai_task — dispatches caption/transcript/face detection for all pending items."""
    from app.workers.tasks.ai import backfill_ai_task
    task = backfill_ai_task.apply_async(queue="ai")
    return {"status": "queued", "task_id": task.id}


@router.get("/faces/task/{task_id}")
async def get_face_task_status(
    task_id: str = Path(...),
    _: None = Auth,
) -> dict:
    """Poll the state of a clustering or backfill Celery task."""
    from app.workers.celery_app import celery_app
    ar = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "state": ar.state,  # PENDING | STARTED | SUCCESS | FAILURE | RETRY
        "result": ar.result if ar.state == "SUCCESS" else None,
        "error": str(ar.result) if ar.state == "FAILURE" else None,
    }


@router.delete("/faces/task/{task_id}", status_code=200)
async def cancel_face_task(
    task_id: str = Path(...),
    _: None = Auth,
) -> dict:
    """Revoke a queued or running task."""
    from app.workers.celery_app import celery_app
    celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
    return {"status": "cancelled", "task_id": task_id}


@router.get("/faces/{face_id}/crop")
async def get_face_crop(
    face_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Return a cropped JPEG of the face bounding box from its media thumbnail."""
    import io
    from PIL import Image as PILImage

    from app.models.media_face import MediaFace
    from app.models.media_item import MediaItem

    face = await db.get(MediaFace, face_id)
    if not face:
        raise HTTPException(status_code=404, detail="Face not found")
    item = await db.get(MediaItem, face.media_id)
    if not item or not item.thumbnail_path:
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    try:
        img = PILImage.open(item.thumbnail_path).convert("RGB")
    except Exception:
        raise HTTPException(status_code=404, detail="Thumbnail unreadable")

    iw, ih = img.size
    # 25% padding around the detected bbox
    pad_x = int(face.bbox_w * 0.25)
    pad_y = int(face.bbox_h * 0.25)
    x1 = max(0, face.bbox_x - pad_x)
    y1 = max(0, face.bbox_y - pad_y)
    x2 = min(iw, face.bbox_x + face.bbox_w + pad_x)
    y2 = min(ih, face.bbox_y + face.bbox_h + pad_y)

    crop = img.crop((x1, y1, x2, y2))
    buf = io.BytesIO()
    crop.save(buf, format="JPEG", quality=85)
    return Response(content=buf.getvalue(), media_type="image/jpeg")


@router.get("/faces/clusters", response_model=list[FaceClusterSchema])
async def list_clusters(
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
) -> list[FaceClusterSchema]:
    """List all face clusters with member count and a representative thumbnail."""
    return await face_service.list_clusters(db, api_v1_prefix=settings.api_v1_prefix)


@router.get("/faces/clusters/{cluster_id}", response_model=FaceClusterMediaResponse)
async def get_cluster_media(
    cluster_id: int,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
) -> FaceClusterMediaResponse:
    """Return paginated media item IDs belonging to a face cluster."""
    media_ids, total = await face_service.get_cluster_media(
        db,
        cluster_id=cluster_id,
        page=page,
        limit=limit,
        api_v1_prefix=settings.api_v1_prefix,
    )
    pages = (total + limit - 1) // limit
    return FaceClusterMediaResponse(
        cluster_id=cluster_id,
        media_ids=media_ids,
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )


@router.get("/media/{media_id}/faces", response_model=list[FaceSchema])
async def get_media_faces(
    media_id: str,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
) -> list[FaceSchema]:
    """Return all detected faces for a specific media item."""
    return await face_service.list_faces_for_media(
        db, media_id=media_id, api_v1_prefix=settings.api_v1_prefix
    )
