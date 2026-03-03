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

cd "$ROOT/infra"

# ── 3. Build images ──────────────────────────────────────────────────────────
echo "🔨 Building images..."
docker compose build

# ── 4. Start DB + Redis, wait for health ─────────────────────────────────────
echo "🐘 Starting database and cache..."
docker compose up -d db redis

echo "⏳ Waiting for database..."
until docker compose exec -T db pg_isready -U indexxxer -d indexxxer -q 2>/dev/null; do
  sleep 1
done
echo "✅ Database ready."

# ── 5. Run Alembic migrations ─────────────────────────────────────────────────
echo "🗄  Running migrations..."
docker compose run --rm --no-deps backend alembic upgrade head
echo "✅ Migrations applied."

# ── 6. Bring up the full stack ───────────────────────────────────────────────
echo "🚀 Starting indexxxer stack..."
docker compose up "$@"
