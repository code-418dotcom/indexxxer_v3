"""Torrent search (Prowlarr) and download (Transmission) API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_db
from app.schemas.torrent import (
    ProwlarrSearchResponse,
    TorrentDownloadRequest,
    TorrentDownloadResponse,
)

router = APIRouter(prefix="/torrents", tags=["torrents"])


def _to_response(dl) -> TorrentDownloadResponse:
    return TorrentDownloadResponse(
        id=dl.id,
        torrent_hash=dl.torrent_hash,
        title=dl.title,
        size=dl.size,
        performer_id=dl.performer_id,
        performer_name=dl.performer.name if dl.performer else None,
        status=dl.status,
        progress=dl.progress,
        source_url=dl.source_url,
        indexer=dl.indexer,
        destination_path=dl.destination_path,
        created_at=dl.created_at,
        completed_at=dl.completed_at,
    )


@router.get("/search")
async def search_prowlarr(
    q: str,
    _user=Depends(get_current_user),
) -> ProwlarrSearchResponse:
    """Search Prowlarr indexers."""
    from app.services import prowlarr_service

    try:
        results = await prowlarr_service.search(q)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Prowlarr error: {e}")

    return ProwlarrSearchResponse(
        query=q,
        results=results,
        count=len(results),
    )


@router.post("/download")
async def start_download(
    body: TorrentDownloadRequest,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> TorrentDownloadResponse:
    """Send a torrent to Transmission and track it."""
    import base64
    import httpx
    from app.services import transmission_service, torrent_download_service

    url = body.magnet_url or body.download_url
    if not url:
        raise HTTPException(400, "Either magnet_url or download_url is required")

    # Magnet links can go directly to Transmission
    # Prowlarr download URLs are proxy links that return .torrent file content —
    # fetch the file and pass as base64 metainfo to Transmission
    try:
        if url.startswith("magnet:"):
            torrent = transmission_service.add_torrent(url)
        else:
            # Prowlarr download URLs either redirect to a magnet link
            # or return .torrent file content. Handle both cases.
            from app.config import settings
            headers = {}
            if settings.prowlarr_url and url.startswith(settings.prowlarr_url):
                headers["X-Api-Key"] = settings.prowlarr_api_key
            async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
                resp = await client.get(url, headers=headers)

            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("location", "")
                if location.startswith("magnet:"):
                    torrent = transmission_service.add_torrent(location)
                else:
                    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                        resp2 = await client.get(location, headers=headers)
                        resp2.raise_for_status()
                    torrent_b64 = base64.b64encode(resp2.content).decode()
                    torrent = transmission_service.add_torrent_base64(torrent_b64)
            elif resp.status_code == 200:
                torrent_b64 = base64.b64encode(resp.content).decode()
                torrent = transmission_service.add_torrent_base64(torrent_b64)
            else:
                resp.raise_for_status()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Transmission error: {e}")

    # Check for duplicate
    existing = await torrent_download_service.get_by_hash(db, torrent.hashString)
    if existing:
        raise HTTPException(409, f"Torrent already tracked: {existing.title}")

    dl = await torrent_download_service.create_download(
        db,
        torrent_hash=torrent.hashString,
        title=body.title,
        size=body.size,
        performer_id=body.performer_id,
        source_url=url,
        indexer=body.indexer,
    )
    await db.commit()
    await db.refresh(dl, ["performer"])

    return _to_response(dl)


@router.get("/active")
async def list_active(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> list[TorrentDownloadResponse]:
    """List in-progress torrent downloads."""
    from app.services import torrent_download_service

    downloads = await torrent_download_service.list_downloads(
        db, statuses=["pending", "downloading", "moving"]
    )

    # Enrich with live progress from Transmission
    try:
        from app.services import transmission_service

        for dl in downloads:
            t = transmission_service.get_torrent(dl.torrent_hash)
            if t:
                dl.progress = round(t.progress, 1)
    except Exception:
        pass  # Transmission unreachable — show DB progress

    return [_to_response(dl) for dl in downloads]


@router.get("/history")
async def list_history(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> list[TorrentDownloadResponse]:
    """List completed and errored downloads."""
    from app.services import torrent_download_service

    downloads = await torrent_download_service.list_downloads(
        db, statuses=["completed", "error"], limit=limit, offset=offset
    )
    return [_to_response(dl) for dl in downloads]


@router.delete("/{download_id}")
async def cancel_download(
    download_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Cancel a download — removes from Transmission and marks as error."""
    from app.services import torrent_download_service, transmission_service

    dl = await torrent_download_service.get_download(db, download_id)
    if not dl:
        raise HTTPException(404, "Download not found")

    try:
        transmission_service.remove_torrent(dl.torrent_hash, delete_data=True)
    except Exception:
        pass  # Already gone from Transmission

    dl.status = "error"
    dl.status_error = "Cancelled by user"
    await db.commit()

    return {"status": "cancelled"}
