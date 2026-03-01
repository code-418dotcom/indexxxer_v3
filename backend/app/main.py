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
    @app.get("/health", tags=["system"], response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", version=APP_VERSION)

    # ── API routers ───────────────────────────────────────────────────────────
    from app.routers import jobs, media, search, sources, tags

    app.include_router(media.router,   prefix=settings.api_v1_prefix)
    app.include_router(search.router,  prefix=settings.api_v1_prefix)
    app.include_router(tags.router,    prefix=settings.api_v1_prefix)
    app.include_router(sources.router, prefix=settings.api_v1_prefix)
    app.include_router(jobs.router,    prefix=settings.api_v1_prefix)

    return app


app = create_app()
