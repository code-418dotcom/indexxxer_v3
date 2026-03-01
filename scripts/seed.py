#!/usr/bin/env python
"""
indexxxer seed script.

Creates the default media source for the configured library path.
Safe to re-run — skips creation if a source at the same path already exists.

Usage (from project root, with backend deps installed):
    cd backend && uv run python ../scripts/seed.py
    # or inside Docker:
    docker compose exec backend python /app/../scripts/seed.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Allow running from project root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.models.media_source import MediaSource

# The path the scanner will see inside the container.
# /mnt/e/media is mounted at /media (read-only) by docker-compose.
# Adjust SEED_SOURCE_PATH in your environment to override.
DEFAULT_SOURCE_PATH = os.environ.get("SEED_SOURCE_PATH", "/media/xxx")
DEFAULT_SOURCE_NAME = os.environ.get("SEED_SOURCE_NAME", "Main Library")

# MIME types and extensions the scanner will include
DEFAULT_SCAN_CONFIG = {
    "include_extensions": [
        # Images
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif",
        ".avif", ".heic", ".heif",
        # Videos
        ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
        ".m4v", ".mpg", ".mpeg", ".3gp", ".ts",
    ],
    "exclude_globs": [
        "**/.DS_Store",
        "**/Thumbs.db",
        "**/desktop.ini",
        "**/*.nfo",
        "**/*.txt",
    ],
    "skip_hidden": True,   # skip files/dirs starting with '.'
    "max_depth": None,     # no depth limit
}


async def seed() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with Session() as session:
        # Check for an existing source at the same path
        result = await session.execute(
            select(MediaSource).where(MediaSource.path == DEFAULT_SOURCE_PATH)
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(
                f"[seed] Source already exists — skipping.\n"
                f"  ID:   {existing.id}\n"
                f"  Name: {existing.name}\n"
                f"  Path: {existing.path}"
            )
        else:
            source = MediaSource(
                name=DEFAULT_SOURCE_NAME,
                path=DEFAULT_SOURCE_PATH,
                source_type="local",
                enabled=True,
                scan_config=DEFAULT_SCAN_CONFIG,
            )
            session.add(source)
            await session.commit()
            print(
                f"[seed] Created default media source.\n"
                f"  ID:   {source.id}\n"
                f"  Name: {source.name}\n"
                f"  Path: {source.path}\n\n"
                f"  Trigger a scan via:\n"
                f"    POST /api/v1/sources/{source.id}/scan"
            )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
