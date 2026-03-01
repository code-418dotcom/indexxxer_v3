from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
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

    # ── File watcher ─────────────────────────────────────────────────────────
    # Use PollingObserver (works on WSL2 + Windows NTFS mounts where inotify fails)
    watcher_use_polling: bool = True
    # Polling interval in seconds (only used when watcher_use_polling=True)
    watcher_poll_interval: int = 60

    # ── CORS ─────────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v: str | list[str]) -> list[str]:
        """Allow CORS_ORIGINS as a comma-separated string in .env."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

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
