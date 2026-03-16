"""
Performer CRUD service and filename/directory matching logic.
"""

import re
from pathlib import PurePosixPath

import structlog
from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import conflict, not_found
from app.core.pagination import PaginationParams, paginate
from app.models.media_item import MediaItem
from app.models.performer import MediaPerformer, Performer
from app.schemas.performer import (
    PerformerCreate,
    PerformerRef,
    PerformerResponse,
    PerformerUpdate,
)
from app.services.storage_service import make_performer_image_url

log = structlog.get_logger(__name__)


# ── Slug helper ──────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    """Convert performer name to URL-safe slug."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# ── Conversion helpers ───────────────────────────────────────────────────────

def to_performer_response(
    p: Performer,
    *,
    video_count: int = 0,
    gallery_count: int = 0,
) -> PerformerResponse:
    return PerformerResponse(
        id=p.id,
        name=p.name,
        slug=p.slug,
        aliases=p.aliases,
        bio=p.bio,
        birthdate=p.birthdate,
        birthplace=p.birthplace,
        nationality=p.nationality,
        ethnicity=p.ethnicity,
        hair_color=p.hair_color,
        eye_color=p.eye_color,
        height=p.height,
        weight=p.weight,
        measurements=p.measurements,
        years_active=p.years_active,
        profile_image_url=make_performer_image_url(p.id) if p.profile_image_path else None,
        freeones_url=p.freeones_url,
        scraped_at=p.scraped_at,
        media_count=p.media_count,
        video_count=video_count,
        gallery_count=gallery_count,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


async def _get_performer_counts(
    db: AsyncSession, performer_ids: list[str]
) -> dict[str, tuple[int, int]]:
    """Return {performer_id: (video_count, gallery_count)} for a batch of performers."""
    if not performer_ids:
        return {}

    # Video count: count media_performers where media_type = 'video'
    video_stmt = (
        select(
            MediaPerformer.performer_id,
            func.count(MediaPerformer.media_id),
        )
        .join(MediaItem, MediaItem.id == MediaPerformer.media_id)
        .where(
            MediaPerformer.performer_id.in_(performer_ids),
            MediaItem.media_type == "video",
        )
        .group_by(MediaPerformer.performer_id)
    )
    video_rows = (await db.execute(video_stmt)).all()
    video_map = {pid: cnt for pid, cnt in video_rows}

    # Gallery count: count matching galleries per performer (via path matching)
    # This is done per-performer using the gallery_service helper, cached for the batch
    from app.models.gallery import Gallery

    all_galleries = (await db.execute(select(Gallery.file_path))).all()
    gallery_paths = [r[0] for r in all_galleries]

    performers = (
        await db.execute(select(Performer).where(Performer.id.in_(performer_ids)))
    ).scalars().all()

    gallery_map: dict[str, int] = {}
    for p in performers:
        patterns = _build_match_patterns(p)
        if not patterns:
            gallery_map[p.id] = 0
            continue
        count = 0
        for gpath in gallery_paths:
            parts = PurePosixPath(gpath).parts
            for part in parts:
                if any(_name_matches(pat, part) for pat in patterns):
                    count += 1
                    break
        gallery_map[p.id] = count

    return {
        pid: (video_map.get(pid, 0), gallery_map.get(pid, 0))
        for pid in performer_ids
    }


def build_performer_refs(media_performers: list[MediaPerformer]) -> list[PerformerRef]:
    """Build lightweight performer refs from junction rows."""
    return [
        PerformerRef(
            id=mp.performer.id,
            name=mp.performer.name,
            slug=mp.performer.slug,
            profile_image_url=(
                make_performer_image_url(mp.performer.id)
                if mp.performer.profile_image_path
                else None
            ),
            match_source=mp.match_source,
            confidence=mp.confidence,
        )
        for mp in media_performers
        if mp.performer is not None
    ]


# ── CRUD ─────────────────────────────────────────────────────────────────────

async def list_performers(
    db: AsyncSession,
    params: PaginationParams,
    q: str | None = None,
    sort: str = "name",
    order: str = "asc",
) -> dict:
    stmt = select(Performer)
    if q:
        stmt = stmt.where(Performer.name.ilike(f"%{q}%"))

    sort_col = {
        "name": Performer.name,
        "media_count": Performer.media_count,
        "created_at": Performer.created_at,
    }.get(sort, Performer.name)
    stmt = stmt.order_by(
        sort_col.asc() if order == "asc" else sort_col.desc()
    )

    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    performers = (
        await db.execute(stmt.offset(params.offset).limit(params.limit))
    ).scalars().all()

    # Batch-compute video and gallery counts
    pids = [p.id for p in performers]
    counts = await _get_performer_counts(db, pids)

    return paginate(
        [
            to_performer_response(
                p,
                video_count=counts.get(p.id, (0, 0))[0],
                gallery_count=counts.get(p.id, (0, 0))[1],
            )
            for p in performers
        ],
        total,
        params,
    )


async def get_performer(db: AsyncSession, performer_id: str) -> PerformerResponse:
    p = await db.get(Performer, performer_id)
    if not p:
        raise not_found("Performer", performer_id)
    counts = await _get_performer_counts(db, [performer_id])
    vc, gc = counts.get(performer_id, (0, 0))
    return to_performer_response(p, video_count=vc, gallery_count=gc)


async def get_performer_by_slug(db: AsyncSession, slug: str) -> Performer | None:
    result = await db.execute(
        select(Performer).where(Performer.slug == slug)
    )
    return result.scalar_one_or_none()


async def create_performer(
    db: AsyncSession, body: PerformerCreate
) -> PerformerResponse:
    slug = slugify(body.name)
    existing = await get_performer_by_slug(db, slug)
    if existing:
        raise conflict(f"Performer with slug '{slug}' already exists")

    performer = Performer(
        name=body.name,
        slug=slug,
        aliases=body.aliases,
        bio=body.bio,
        birthdate=body.birthdate,
        birthplace=body.birthplace,
        nationality=body.nationality,
        ethnicity=body.ethnicity,
        hair_color=body.hair_color,
        eye_color=body.eye_color,
        height=body.height,
        weight=body.weight,
        measurements=body.measurements,
        years_active=body.years_active,
        freeones_url=body.freeones_url,
    )
    db.add(performer)
    await db.flush()
    await db.refresh(performer)
    return to_performer_response(performer)


async def update_performer(
    db: AsyncSession, performer_id: str, body: PerformerUpdate
) -> PerformerResponse:
    p = await db.get(Performer, performer_id)
    if not p:
        raise not_found("Performer", performer_id)

    update_data = body.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"] is not None:
        p.slug = slugify(update_data["name"])

    for field_name, value in update_data.items():
        setattr(p, field_name, value)

    await db.flush()
    await db.refresh(p)
    return to_performer_response(p)


async def delete_performer(db: AsyncSession, performer_id: str) -> None:
    p = await db.get(Performer, performer_id)
    if not p:
        raise not_found("Performer", performer_id)
    await db.delete(p)
    await db.flush()


# ── Media for performer ──────────────────────────────────────────────────────

async def get_performer_media_ids(
    db: AsyncSession, performer_id: str
) -> list[str]:
    """Return all media_item IDs linked to a performer."""
    result = await db.execute(
        select(MediaPerformer.media_id).where(
            MediaPerformer.performer_id == performer_id
        )
    )
    return [r[0] for r in result.all()]


# ── Matching logic ───────────────────────────────────────────────────────────

def _build_match_patterns(performer: Performer) -> list[str]:
    """
    Build a list of name patterns to match against filenames/directories.

    Returns lowercased patterns. Each pattern is matched as a word boundary
    in the target string, with spaces/hyphens/underscores interchangeable.
    """
    names: list[str] = [performer.name]
    if performer.aliases:
        names.extend(performer.aliases)

    patterns = []
    for name in names:
        if not name:
            continue
        # Normalise: lowercase, strip extra whitespace
        normalised = name.strip().lower()
        if len(normalised) < 2:
            continue
        patterns.append(normalised)

    return patterns


def _name_matches(pattern: str, target: str) -> bool:
    """
    Check if a performer name pattern matches a target string.

    Handles spaces, hyphens, underscores, and dots as interchangeable separators.
    Uses word boundary matching to avoid false positives.
    """
    # Normalise target: lowercase
    target_lower = target.lower()

    # Build regex: replace separators in pattern with flexible separator match
    # "mia khalifa" should match "mia.khalifa", "mia-khalifa", "mia_khalifa"
    escaped = re.escape(pattern)
    # Replace escaped separator characters with flexible separator class
    flex_pattern = re.sub(r"[\\ .\-_]+", r"[\\s._\\-]+", escaped)

    # Word boundary match (allow start/end of string or separator chars)
    regex = rf"(?:^|[\s._\-\(\)\[\]]){flex_pattern}(?:$|[\s._\-\(\)\[\]])"

    return bool(re.search(regex, target_lower))


async def match_performer_to_media(
    db: AsyncSession,
    performer: Performer,
    *,
    limit: int | None = None,
) -> int:
    """
    Match a single performer against all media items by filename and directory.

    Returns the number of new links created.
    """
    patterns = _build_match_patterns(performer)
    if not patterns:
        return 0

    # Get all media items (id, filename, file_path)
    stmt = select(MediaItem.id, MediaItem.filename, MediaItem.file_path)
    if limit:
        stmt = stmt.limit(limit)
    rows = (await db.execute(stmt)).all()

    # Get existing links to avoid duplicates
    existing = set()
    result = await db.execute(
        select(MediaPerformer.media_id).where(
            MediaPerformer.performer_id == performer.id
        )
    )
    for r in result.all():
        existing.add(r[0])

    new_links = 0
    for media_id, filename, file_path in rows:
        if media_id in existing:
            continue

        # Check filename (without extension)
        stem = PurePosixPath(filename).stem
        for pattern in patterns:
            if _name_matches(pattern, stem):
                db.add(
                    MediaPerformer(
                        media_id=media_id,
                        performer_id=performer.id,
                        match_source="filename",
                        confidence=1.0,
                    )
                )
                existing.add(media_id)
                new_links += 1
                break
        else:
            # Check directory names in the path
            parts = PurePosixPath(file_path).parts[:-1]  # exclude filename
            for part in parts:
                matched = False
                for pattern in patterns:
                    if _name_matches(pattern, part):
                        db.add(
                            MediaPerformer(
                                media_id=media_id,
                                performer_id=performer.id,
                                match_source="directory",
                                confidence=0.9,
                            )
                        )
                        existing.add(media_id)
                        new_links += 1
                        matched = True
                        break
                if matched:
                    break

    if new_links:
        await db.flush()
        # Update denormalized count
        count = (
            await db.execute(
                select(func.count()).where(
                    MediaPerformer.performer_id == performer.id
                )
            )
        ).scalar_one()
        performer.media_count = count
        await db.flush()

    log.info(
        "performer.match_complete",
        performer=performer.name,
        new_links=new_links,
        total_media=len(rows),
    )
    return new_links


async def match_all_performers(db: AsyncSession) -> dict[str, int]:
    """Match all performers against all media. Returns {performer_name: new_links}."""
    performers = (await db.execute(select(Performer))).scalars().all()
    results = {}
    for p in performers:
        n = await match_performer_to_media(db, p)
        if n > 0:
            results[p.name] = n
    return results


async def match_media_item_to_performers(
    db: AsyncSession,
    media_id: str,
    filename: str,
    file_path: str,
) -> int:
    """
    Match a single media item against all known performers.
    Called during the scan pipeline for auto-matching.
    Returns number of performers matched.
    """
    performers = (await db.execute(select(Performer))).scalars().all()
    if not performers:
        return 0

    stem = PurePosixPath(filename).stem
    parts = PurePosixPath(file_path).parts[:-1]
    matched = 0

    for performer in performers:
        patterns = _build_match_patterns(performer)
        if not patterns:
            continue

        # Check if link already exists
        existing = await db.execute(
            select(MediaPerformer).where(
                MediaPerformer.media_id == media_id,
                MediaPerformer.performer_id == performer.id,
            )
        )
        if existing.scalar_one_or_none():
            continue

        link_source = None
        confidence = 1.0

        # Check filename
        for pattern in patterns:
            if _name_matches(pattern, stem):
                link_source = "filename"
                break

        # Check directories
        if not link_source:
            for part in parts:
                for pattern in patterns:
                    if _name_matches(pattern, part):
                        link_source = "directory"
                        confidence = 0.9
                        break
                if link_source:
                    break

        if link_source:
            db.add(
                MediaPerformer(
                    media_id=media_id,
                    performer_id=performer.id,
                    match_source=link_source,
                    confidence=confidence,
                )
            )
            # Update denormalized count
            performer.media_count = (
                await db.execute(
                    select(func.count()).where(
                        MediaPerformer.performer_id == performer.id
                    )
                )
            ).scalar_one() + 1
            matched += 1

    if matched:
        await db.flush()

    return matched


async def refresh_media_counts(db: AsyncSession) -> None:
    """Recalculate media_count for all performers."""
    performers = (await db.execute(select(Performer))).scalars().all()
    for p in performers:
        count = (
            await db.execute(
                select(func.count()).where(
                    MediaPerformer.performer_id == p.id
                )
            )
        ).scalar_one()
        p.media_count = count
    await db.flush()
