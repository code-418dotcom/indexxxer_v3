# syntax=docker/dockerfile:1
# GPU worker image for CLIP embedding computation.
# Base: NVIDIA CUDA 12.4 + cuDNN 9 runtime on Ubuntu 22.04
# Uses uv for fast Python dependency installation.
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04 AS base

# Install system dependencies (uv manages Python itself)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install uv (downloads and manages Python 3.12)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:/opt/venv/bin:$PATH"

WORKDIR /app

# Put venv outside /app so the dev volume mount doesn't shadow it
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Install base deps + ml extras (open-clip-torch pulls torch+CUDA)
COPY pyproject.toml .
RUN uv sync --no-install-project --extra ml --no-dev

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Source is mounted at /app via docker-compose volume in dev
CMD ["celery", "-A", "app.workers.celery_app", "worker", \
     "--loglevel=info", "--queues=ml", "--concurrency=1", "--hostname=gpu_worker@%h"]
