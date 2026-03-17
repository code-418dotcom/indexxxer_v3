"""Schemas for Prowlarr search + Transmission torrent downloads."""

from datetime import datetime

from pydantic import BaseModel


class ProwlarrResult(BaseModel):
    title: str
    size: int
    seeders: int
    leechers: int
    age: str
    magnet_url: str | None = None
    download_url: str | None = None
    indexer: str
    categories: list[str] = []
    info_url: str | None = None


class ProwlarrSearchResponse(BaseModel):
    query: str
    results: list[ProwlarrResult]
    count: int


class TorrentDownloadRequest(BaseModel):
    title: str
    magnet_url: str | None = None
    download_url: str | None = None
    performer_id: str
    size: int | None = None
    indexer: str | None = None


class TorrentDownloadResponse(BaseModel):
    id: str
    torrent_hash: str
    title: str
    size: int | None
    performer_id: str | None
    performer_name: str | None = None
    status: str
    progress: float
    source_url: str | None
    indexer: str | None
    destination_path: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
