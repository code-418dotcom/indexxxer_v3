"""Prowlarr API client for indexer search."""

from __future__ import annotations

import httpx
import structlog

from app.config import settings

log = structlog.get_logger(__name__)


async def search(
    query: str,
    indexer_ids: list[int] | None = None,
) -> list[dict]:
    """Search Prowlarr indexers and return normalized results."""
    if not settings.prowlarr_url:
        raise ValueError("Prowlarr is not configured (PROWLARR_URL is empty)")

    params: dict = {"query": query}
    if indexer_ids:
        params["indexerIds"] = ",".join(str(i) for i in indexer_ids)
    else:
        # -2 = all torrent indexers
        params["indexerIds"] = "-2"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{settings.prowlarr_url}/api/v1/search",
            params=params,
            headers={"X-Api-Key": settings.prowlarr_api_key},
        )
        resp.raise_for_status()
        raw = resp.json()

    results = []
    for item in raw:
        # Calculate age string from publishDate
        age = item.get("age", 0)
        if isinstance(age, (int, float)):
            age_str = f"{int(age)}d" if age else "new"
        else:
            age_str = str(age)

        results.append(
            {
                "title": item.get("title", ""),
                "size": item.get("size", 0),
                "seeders": item.get("seeders", 0),
                "leechers": item.get("leechers", 0),
                "age": age_str,
                "magnet_url": item.get("magnetUrl") or None,
                "download_url": item.get("downloadUrl") or None,
                "indexer": item.get("indexer", ""),
                "categories": [
                    c.get("name", "") for c in (item.get("categories") or [])
                ],
                "info_url": item.get("infoUrl") or None,
            }
        )

    log.info("prowlarr.search", query=query, results=len(results))
    return results


async def get_indexers() -> list[dict]:
    """List configured Prowlarr indexers."""
    if not settings.prowlarr_url:
        return []

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{settings.prowlarr_url}/api/v1/indexer",
            headers={"X-Api-Key": settings.prowlarr_api_key},
        )
        resp.raise_for_status()
        raw = resp.json()

    return [
        {"id": ix.get("id"), "name": ix.get("name"), "protocol": ix.get("protocol")}
        for ix in raw
    ]
