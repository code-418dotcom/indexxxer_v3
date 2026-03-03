"""Business logic for face cluster queries."""

from __future__ import annotations

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media_face import MediaFace
from app.models.media_item import MediaItem
from app.schemas.face import FaceClusterSchema, FaceSchema, FaceStatsSchema


async def list_faces_for_media(
    session: AsyncSession,
    media_id: str,
    api_v1_prefix: str,
) -> list[FaceSchema]:
    """Return all detected faces for a single MediaItem."""
    result = await session.execute(
        select(MediaFace).where(MediaFace.media_id == media_id).order_by(MediaFace.confidence.desc())
    )
    return [FaceSchema.model_validate(f) for f in result.scalars()]


async def list_clusters(
    session: AsyncSession,
    api_v1_prefix: str,
) -> list[FaceClusterSchema]:
    """
    Return one entry per cluster_id with member count and a representative
    media item (the face with highest confidence in that cluster).
    """
    # Aggregate cluster stats
    stats_result = await session.execute(
        select(
            MediaFace.cluster_id,
            func.count(MediaFace.id).label("member_count"),
        )
        .where(MediaFace.cluster_id.isnot(None))
        .group_by(MediaFace.cluster_id)
        .order_by(MediaFace.cluster_id)
    )
    stats = {row.cluster_id: row.member_count for row in stats_result}

    if not stats:
        return []

    # Find the representative face (highest confidence) per cluster
    rep_result = await session.execute(
        text(
            """
            SELECT DISTINCT ON (cluster_id)
                cluster_id,
                id AS face_id,
                media_id,
                confidence
            FROM media_faces
            WHERE cluster_id IS NOT NULL
            ORDER BY cluster_id, confidence DESC
            """
        )
    )
    reps = {row.cluster_id: (row.face_id, row.media_id) for row in rep_result}

    # Fetch thumbnail info for representative media items
    rep_media_ids = list({media_id for _, media_id in reps.values()})
    media_result = await session.execute(
        select(MediaItem.id, MediaItem.thumbnail_path).where(MediaItem.id.in_(rep_media_ids))
    )
    thumbnails = {row.id: row.thumbnail_path for row in media_result}

    clusters: list[FaceClusterSchema] = []
    for cluster_id, member_count in stats.items():
        rep = reps.get(cluster_id)
        if rep is None:
            clusters.append(FaceClusterSchema(cluster_id=cluster_id, member_count=member_count))
            continue
        face_id, rep_media_id = rep
        has_thumb = thumbnails.get(rep_media_id)
        clusters.append(
            FaceClusterSchema(
                cluster_id=cluster_id,
                member_count=member_count,
                representative_media_id=rep_media_id,
                representative_face_id=face_id,
                face_crop_url=f"{api_v1_prefix}/faces/{face_id}/crop",
                representative_thumbnail_url=(
                    f"{api_v1_prefix}/media/{rep_media_id}/thumbnail" if has_thumb else None
                ),
            )
        )
    return clusters


async def get_stats(session: AsyncSession) -> FaceStatsSchema:
    """Return aggregate counts for faces and clusters."""
    total = await session.scalar(select(func.count(MediaFace.id))) or 0
    unclustered = (
        await session.scalar(
            select(func.count(MediaFace.id)).where(MediaFace.cluster_id.is_(None))
        )
        or 0
    )
    cluster_count = (
        await session.scalar(
            select(func.count(func.distinct(MediaFace.cluster_id))).where(
                MediaFace.cluster_id.isnot(None)
            )
        )
        or 0
    )
    return FaceStatsSchema(
        total_faces=total,
        unclustered=unclustered,
        cluster_count=cluster_count,
    )


async def get_cluster_media(
    session: AsyncSession,
    cluster_id: int,
    page: int,
    limit: int,
    api_v1_prefix: str,
) -> tuple[list[str], int]:
    """
    Return (media_ids, total) for a cluster, paginated.
    Callers can then hydrate full MediaItem details as needed.
    """
    count_result = await session.execute(
        select(func.count(func.distinct(MediaFace.media_id))).where(
            MediaFace.cluster_id == cluster_id
        )
    )
    total = count_result.scalar_one()

    ids_result = await session.execute(
        select(func.distinct(MediaFace.media_id))
        .where(MediaFace.cluster_id == cluster_id)
        .offset((page - 1) * limit)
        .limit(limit)
    )
    return [str(row[0]) for row in ids_result], total
