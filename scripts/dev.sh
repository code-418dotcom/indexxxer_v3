#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# indexxxer dev bootstrap
# Run from the project root: ./scripts/dev.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/.env"
THUMBNAIL_DIR="$ROOT/data/thumbnails"

# ── 1. Ensure .env exists ────────────────────────────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
  echo "⚠  .env not found — copying from .env.example"
  cp "$ROOT/.env.example" "$ENV_FILE"
  echo "✅ .env created. Edit it to set API_TOKEN before continuing."
  echo "   nano $ENV_FILE"
  exit 1
fi

# ── 2. Ensure thumbnail directory exists ─────────────────────────────────────
mkdir -p "$THUMBNAIL_DIR"
echo "📁 Thumbnail dir: $THUMBNAIL_DIR"

# ── 3. Bring up services ─────────────────────────────────────────────────────
echo "🚀 Starting indexxxer stack..."
cd "$ROOT/infra"
docker compose up --build "$@"
