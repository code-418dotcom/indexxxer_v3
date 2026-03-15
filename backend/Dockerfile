# syntax=docker/dockerfile:1
# Uses the official uv image (Python 3.12 + uv pre-installed, Debian Bookworm slim base)
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base

WORKDIR /app

# System deps: ffmpeg for video processing, libgl1 for Pillow/OpenCV later
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Put the venv outside /app so the dev volume mount doesn't shadow it.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies.
# Without a uv.lock file present, uv generates one inside the layer (not persisted to host).
# Run `uv lock` locally and commit uv.lock when pinning production deps.
COPY pyproject.toml .
RUN uv sync --no-install-project --no-dev
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install Playwright Chromium for performer scraping
RUN playwright install --with-deps chromium

# ── development target ─────────────────────────────────────────────────────────
# Source code is mounted at /app via docker-compose volume; no COPY needed.
FROM base AS dev
# Also install dev deps (pytest, ruff, etc.)
RUN uv sync --no-install-project
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── production target ──────────────────────────────────────────────────────────
FROM base AS prod
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
