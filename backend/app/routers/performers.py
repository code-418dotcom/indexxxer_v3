"""
Performer CRUD endpoints, scraping, matching, and image serving.

IMPORTANT: Literal routes (/scrape-new, /scrape-all, /match-all) are defined
BEFORE parameterised routes (/{performer_id}) to avoid FastAPI matching
"scrape-all" as a performer_id.
"""

import asyncio
import json
import shutil
import uuid
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import Auth
from app.core.exceptions import bad_request, not_found
from app.core.pagination import PaginatedResponse, PaginationParams, paginate
from app.core.security import decode_token
from app.database import get_db
from app.models.performer import Performer
from app.schemas.media_item import MediaItemSummary
from app.schemas.performer import (
    PerformerCreate,
    PerformerResponse,
    PerformerUpdate,
    ScrapeRequest,
)
from app.services import gallery_service, media_service, performer_service
from app.services.storage_service import get_performer_image_path

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/performers", tags=["performers"])


# ══════════════════════════════════════════════════════════════════════════════
# LITERAL routes (must come before /{performer_id} to avoid path conflicts)
# ══════════════════════════════════════════════════════════════════════════════


@router.get("", response_model=PaginatedResponse[PerformerResponse])
async def list_performers(
    q: str | None = Query(None, description="Name substring filter"),
    sort: str = Query("name", description="Sort by: name, media_count, created_at"),
    order: str = Query("asc", description="asc or desc"),
    params: PaginationParams = Depends(),
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    return await performer_service.list_performers(db, params, q=q, sort=sort, order=order)


@router.post("", response_model=PerformerResponse, status_code=status.HTTP_201_CREATED)
async def create_performer(
    body: PerformerCreate,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    result = await performer_service.create_performer(db, body)

    if body.freeones_url:
        from app.workers.tasks.performer import scrape_performer_task
        scrape_performer_task.apply_async(
            kwargs={"performer_id": result.id}, queue="indexing"
        )

    from app.workers.tasks.performer import match_performer_task
    match_performer_task.apply_async(
        kwargs={"performer_id": result.id}, queue="indexing", countdown=5
    )

    return result


# ── Scrape new (literal, before /{performer_id}) ─────────────────────────────

@router.post("/scrape-new", response_model=PerformerResponse)
async def scrape_new_performer(
    body: ScrapeRequest,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    """Create a new performer and scrape from freeones. Provide name or freeones_url."""
    if not body.name and not body.freeones_url:
        raise bad_request("Provide either name or freeones_url")

    name = body.name or "Unknown"
    if not body.name and body.freeones_url:
        slug_part = body.freeones_url.rstrip("/").split("/")[-1]
        for suffix in ("bio", "videos", "links", "photos"):
            if slug_part == suffix:
                slug_part = body.freeones_url.rstrip("/").split("/")[-2]
                break
        name = slug_part.replace("-", " ").title()

    from app.schemas.performer import PerformerCreate
    create_body = PerformerCreate(name=name, freeones_url=body.freeones_url)
    result = await performer_service.create_performer(db, create_body)

    from app.workers.tasks.performer import scrape_performer_task
    scrape_performer_task.apply_async(
        kwargs={"performer_id": result.id}, queue="indexing"
    )
    from app.workers.tasks.performer import match_performer_task
    match_performer_task.apply_async(
        kwargs={"performer_id": result.id}, queue="indexing", countdown=5
    )

    return result


# ── Scrape all (literal) ─────────────────────────────────────────────────────

@router.post("/scrape-all")
async def scrape_all_performers(
    _: None = Auth,
):
    """Trigger scraping for ALL performers. Returns a task_id for progress streaming."""
    task_id = str(uuid.uuid4())
    from app.workers.tasks.performer import scrape_all_performers_task
    scrape_all_performers_task.apply_async(
        kwargs={"task_id": task_id}, queue="indexing"
    )
    return {"status": "queued", "task_id": task_id}


def _validate_token(token: str) -> bool:
    from jose import JWTError
    try:
        payload = decode_token(token)
        return payload.get("type") == "access"
    except JWTError:
        pass
    return token == settings.api_token


@router.get(
    "/scrape-all/stream",
    summary="Stream scrape-all progress via SSE",
    response_class=StreamingResponse,
)
async def stream_scrape_all(
    request: Request,
    task_id: str = Query(description="Task ID from /scrape-all response"),
    token: str = Query(description="Auth token (EventSource cannot send headers)"),
    from_id: str = Query(default="0", description="Resume from Redis stream ID"),
):
    """SSE endpoint for scrape-all progress events."""
    if not _validate_token(token):
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid token")

    async def event_generator():
        from redis.asyncio import Redis
        r: Redis = Redis.from_url(settings.redis_url, decode_responses=True)
        stream_key = f"scrape-all:{task_id}"
        last_id = from_id

        try:
            yield f"data: {json.dumps({'type': 'stream.connected', 'task_id': task_id})}\n\n"

            while True:
                if await request.is_disconnected():
                    break

                results = await r.xread(
                    {stream_key: last_id},
                    count=50,
                    block=2000,
                )

                if results:
                    for _stream_name, messages in results:
                        for msg_id, msg_fields in messages:
                            last_id = msg_id
                            raw = msg_fields.get("data", "{}")
                            yield f"data: {raw}\n\n"

                            try:
                                parsed = json.loads(raw)
                                if parsed.get("type") == "scrape_all.complete":
                                    yield f"data: {json.dumps({'type': 'stream.end', 'task_id': task_id})}\n\n"
                                    return
                            except json.JSONDecodeError:
                                pass

                await asyncio.sleep(0)

        except asyncio.CancelledError:
            pass
        finally:
            await r.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Match all (literal) ──────────────────────────────────────────────────────

@router.post("/match-all")
async def match_all_performers(
    _: None = Auth,
):
    """Trigger matching for all performers against all media."""
    from app.workers.tasks.performer import match_all_performers_task
    match_all_performers_task.apply_async(queue="indexing")
    return {"status": "queued"}


# ══════════════════════════════════════════════════════════════════════════════
# PARAMETERISED routes (/{performer_id}/...)
# ══════════════════════════════════════════════════════════════════════════════


@router.get("/{performer_id}", response_model=PerformerResponse)
async def get_performer(
    performer_id: str,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    return await performer_service.get_performer(db, performer_id)


@router.put("/{performer_id}", response_model=PerformerResponse)
async def update_performer(
    performer_id: str,
    body: PerformerUpdate,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    return await performer_service.update_performer(db, performer_id, body)


@router.delete("/{performer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_performer(
    performer_id: str,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    await performer_service.delete_performer(db, performer_id)


# ── Performer image ──────────────────────────────────────────────────────────

@router.get("/{performer_id}/image")
async def get_performer_image(
    performer_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Serve the performer's profile image. No auth required (like thumbnails)."""
    p = await db.get(Performer, performer_id)
    if not p:
        raise not_found("Performer", performer_id)

    img_path = get_performer_image_path(performer_id)
    if not img_path.exists():
        raise not_found("Performer image", performer_id)

    return FileResponse(img_path, media_type="image/jpeg")


@router.put("/{performer_id}/image", response_model=PerformerResponse)
async def upload_performer_image(
    performer_id: str,
    file: UploadFile,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    """Upload or replace a performer's profile image."""
    p = await db.get(Performer, performer_id)
    if not p:
        raise not_found("Performer", performer_id)

    if not file.content_type or not file.content_type.startswith("image/"):
        raise bad_request("File must be an image")

    dest = get_performer_image_path(performer_id)
    dest.parent.mkdir(parents=True, exist_ok=True)

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    p.profile_image_path = str(dest)
    await db.flush()
    await db.refresh(p)
    return performer_service.to_performer_response(p)


# ── Scrape single ────────────────────────────────────────────────────────────

@router.post("/{performer_id}/scrape")
async def scrape_performer(
    performer_id: str,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a freeones.com scrape for this performer."""
    p = await db.get(Performer, performer_id)
    if not p:
        raise not_found("Performer", performer_id)

    from app.workers.tasks.performer import scrape_performer_task
    scrape_performer_task.apply_async(
        kwargs={"performer_id": performer_id}, queue="indexing"
    )
    return {"status": "queued", "performer_id": performer_id}


# ── Match single ─────────────────────────────────────────────────────────────

@router.post("/{performer_id}/match")
async def match_performer(
    performer_id: str,
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    """Trigger filename/directory matching for this performer."""
    p = await db.get(Performer, performer_id)
    if not p:
        raise not_found("Performer", performer_id)

    from app.workers.tasks.performer import match_performer_task
    match_performer_task.apply_async(
        kwargs={"performer_id": performer_id}, queue="indexing"
    )
    return {"status": "queued", "performer_id": performer_id}


# ── Performer media ──────────────────────────────────────────────────────────

@router.get("/{performer_id}/media", response_model=PaginatedResponse[MediaItemSummary])
async def get_performer_media(
    performer_id: str,
    type: str | None = None,
    params: PaginationParams = Depends(),
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    """Return media items linked to this performer (paginated). Filter by type=image|video."""
    p = await db.get(Performer, performer_id)
    if not p:
        raise not_found("Performer", performer_id)

    return await media_service.list_media(
        db, params, performer_id=performer_id, media_type=type or None
    )


@router.get("/{performer_id}/galleries", response_model=dict)
async def get_performer_galleries(
    performer_id: str,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=48, ge=1, le=200),
    _: None = Auth,
    db: AsyncSession = Depends(get_db),
):
    """Return galleries whose path matches this performer's name/aliases."""
    p = await db.get(Performer, performer_id)
    if not p:
        raise not_found("Performer", performer_id)

    items, total = await gallery_service.list_galleries_for_performer(
        db, performer_id, api_v1_prefix=settings.api_v1_prefix, page=page, limit=limit
    )
    pages = (total + limit - 1) // limit if total else 0
    return {
        "items": [i.model_dump() for i in items],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }
