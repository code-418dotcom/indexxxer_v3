"""
indexxxer — FastAPI application factory.

Phase 1: skeleton with health check and CORS.
Routers are registered here as each phase completes.
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings

log = structlog.get_logger(__name__)

APP_VERSION = "0.1.0"


class HealthResponse(BaseModel):
    status: str
    version: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle hook."""
    log.info("indexxxer.start", version=APP_VERSION, debug=settings.debug)

    # Ensure thumbnail root exists at startup
    settings.thumbnail_root_path.mkdir(parents=True, exist_ok=True)
    log.info("thumbnail_root.ready", path=settings.thumbnail_root)

    # Ensure performer image directory exists
    from app.services.storage_service import get_performer_image_dir
    get_performer_image_dir().mkdir(parents=True, exist_ok=True)

    # Seed admin user if no users exist (silently skip if DB not yet migrated)
    try:
        from app.database import AsyncSessionLocal
        from app.services import user_service
        async with AsyncSessionLocal() as db:
            async with db.begin():
                await user_service.seed_admin(db)
    except Exception as exc:
        log.warning("admin.seed_skipped", reason=str(exc))

    yield

    log.info("indexxxer.stop")


def create_app() -> FastAPI:
    app = FastAPI(
        title="indexxxer",
        version=APP_VERSION,
        description="Media indexing and search platform",
        docs_url=f"{settings.api_v1_prefix}/docs",
        redoc_url=f"{settings.api_v1_prefix}/redoc",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Health check (unauthenticated) ────────────────────────────────────────
    # Registered at both paths:
    #   /health            — for Docker healthchecks / curl
    #   /api/v1/health     — for the frontend (proxied via Next.js /api/* rewrite)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", version=APP_VERSION)

    app.add_api_route("/health", health, tags=["system"], response_model=HealthResponse, include_in_schema=False)
    app.add_api_route(f"{settings.api_v1_prefix}/health", health, tags=["system"], response_model=HealthResponse)

    # ── API routers ───────────────────────────────────────────────────────────
    from app.routers import (
        analytics,
        auth,
        downloader,
        duplicates,
        export,
        filters,
        galleries,
        jobs,
        media,
        pdfs,
        performers,
        search,
        sources,
        stream,
        tags,
        torrents,
        users,
        webhooks,
        status,
        workers,
    )

    app.include_router(auth.router,      prefix=settings.api_v1_prefix)
    app.include_router(users.router,     prefix=settings.api_v1_prefix)
    app.include_router(media.router,     prefix=settings.api_v1_prefix)
    app.include_router(search.router,    prefix=settings.api_v1_prefix)
    app.include_router(tags.router,      prefix=settings.api_v1_prefix)
    app.include_router(sources.router,   prefix=settings.api_v1_prefix)
    app.include_router(jobs.router,      prefix=settings.api_v1_prefix)
    app.include_router(stream.router,    prefix=settings.api_v1_prefix)
    app.include_router(filters.router,   prefix=settings.api_v1_prefix)
    app.include_router(export.router,    prefix=settings.api_v1_prefix)
    app.include_router(performers.router, prefix=settings.api_v1_prefix)
    app.include_router(galleries.router, prefix=settings.api_v1_prefix)
    app.include_router(pdfs.router,      prefix=settings.api_v1_prefix)
    app.include_router(workers.router,   prefix=settings.api_v1_prefix)
    app.include_router(webhooks.router,  prefix=settings.api_v1_prefix)
    app.include_router(duplicates.router, prefix=settings.api_v1_prefix)
    app.include_router(downloader.router, prefix=settings.api_v1_prefix)
    app.include_router(torrents.router,  prefix=settings.api_v1_prefix)
    app.include_router(analytics.router, prefix=settings.api_v1_prefix)
    app.include_router(status.router,    prefix=settings.api_v1_prefix)

    # ── GraphQL ───────────────────────────────────────────────────────────────
    from app.graphql.schema import graphql_router
    app.include_router(graphql_router, prefix=f"{settings.api_v1_prefix}/graphql")

    return app


app = create_app()
