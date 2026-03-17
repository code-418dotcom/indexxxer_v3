from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── API ──────────────────────────────────────────────────────────────────
    api_token: str
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = (
        "postgresql+asyncpg://indexxxer:indexxxer_dev@db:5432/indexxxer"
    )

    # ── Redis / Celery ───────────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    # ── Media paths ──────────────────────────────────────────────────────────
    # Root directory where source media lives (mounted read-only in Docker)
    media_root: str = "/media"
    # Root directory for generated thumbnails (writable)
    thumbnail_root: str = "/data/thumbnails"
    # Thumbnail dimensions (max width × height, preserves aspect ratio)
    thumbnail_width: int = 320
    thumbnail_height: int = 240

    # ── Indexing ─────────────────────────────────────────────────────────────
    # Number of concurrent Celery thumbnail workers
    thumbnail_concurrency: int = 4
    # Celery task time limit for thumbnail generation (seconds)
    thumbnail_time_limit: int = 60
    # Celery task time limit for SHA-256 hashing (seconds, 3TB worst-case)
    hash_time_limit: int = 300

    # ── M4 Auth / JWT ────────────────────────────────────────────────────────
    jwt_secret: str = "change-me-jwt-secret"
    jwt_expire_minutes: int = 60
    jwt_refresh_expire_days: int = 30
    admin_email: str = "admin@indexxxer.local"
    admin_password: str = "changeme"

    # ── M4 Encryption (Fernet) ────────────────────────────────────────────────
    # Generate once: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    encryption_key: str = ""

    # ── M4 Webhooks ──────────────────────────────────────────────────────────
    webhook_secret: str = "change-me-webhook-secret"

    # ── Prowlarr ─────────────────────────────────────────────────────────────
    prowlarr_url: str = ""                       # e.g. "http://prowlarr:9696"
    prowlarr_api_key: str = ""

    # ── Transmission ─────────────────────────────────────────────────────────
    transmission_host: str = "transmission"
    transmission_port: int = 9091
    transmission_username: str = ""
    transmission_password: str = ""
    torrent_download_dir: str = "/downloads/indexxxer"
    torrent_destination_root: str = "/media/xxx/Downloader"

    # ── NSFW AI Tagger ─────────────────────────────────────────────────────
    nsfw_tagger_url: str = "http://nsfw_tagger:8000"
    nsfw_tagger_threshold: float = 0.4
    nsfw_tagger_frame_interval: float = 2.0

    # ── File watcher ─────────────────────────────────────────────────────────
    # Use PollingObserver (works on WSL2 + Windows NTFS mounts where inotify fails)
    watcher_use_polling: bool = True
    # Polling interval in seconds (only used when watcher_use_polling=True)
    watcher_poll_interval: int = 60

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Must be a JSON array in .env: CORS_ORIGINS=["http://localhost:3000"]
    # pydantic-settings JSON-decodes list fields before validators run.
    cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def thumbnail_root_path(self) -> Path:
        return Path(self.thumbnail_root)

    @property
    def media_root_path(self) -> Path:
        return Path(self.media_root)


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Module-level singleton — use `from app.config import settings`
settings: Settings = get_settings()
