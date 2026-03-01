# indexxxer_v3 — Milestone 1 Implementation Plan

> M1 Goal: A working, deployable system that can scan a directory, index media files,
> and let authenticated users search and browse them via a web UI.
>
> Status: PHASE 4 COMPLETE — Phase 5 (Frontend) next
> Last updated: 2026-03-01

---

## M1 Scope (recap)

| # | Feature |
|---|---------|
| 1 | Docker Compose local dev stack (PostgreSQL, Redis, MinIO, Traefik) |
| 2 | Alembic-managed PostgreSQL schema |
| 3 | FastAPI REST API — media CRUD, tags, sources, jobs, auth |
| 4 | Static API token auth (`X-API-Token` header) — single-user, no login UI |
| 5 | Celery + Redis worker pool for indexing |
| 6 | Filesystem scanner (local paths) |
| 7 | Metadata extraction (ffprobe for video, Pillow+exifread for images — no audio) |
| 8 | Thumbnail generation (images + video keyframes via ffmpeg) |
| 9 | Incremental file watcher (watchdog) |
| 10 | Full-text search via PostgreSQL tsvector |
| 11 | Next.js 15 frontend: grid/list view, search bar, dark mode, basic filters |

---

## M1 Phases

### Phase 1 — Infrastructure & Skeleton (Week 1) ✅ COMPLETE
Set up Docker Compose stack, project scaffolding, CI skeleton, and empty API that boots.

**Delivered:**
- `.gitignore`, `.env.example`
- `backend/`: `pyproject.toml`, `Dockerfile` (multi-stage dev/prod), `app/main.py`, `app/config.py`, `app/database.py`, `app/core/` (deps, exceptions, pagination), all ORM models, `alembic/env.py`
- `infra/docker-compose.yml` — services: db, redis, backend, worker, frontend
- `frontend/`: `package.json`, `next.config.ts`, `tsconfig.json`, `tailwind.config.ts`, `postcss.config.mjs`, minimal app shell with ThemeProvider and dark mode
- `scripts/dev.sh` — bootstrap helper

### Phase 2 — Data Layer (Week 1–2) ✅ COMPLETE
Database schema, ORM models, Alembic migrations, seed data script.

**Delivered:**
- FK constraints added to `MediaItem`, `IndexJob`, `MediaTag` models
- `alembic/versions/0001_initial_schema.py` — all tables + tsvector trigger + all indexes
- `scripts/seed.py` — idempotent; creates default source at `/media/xxx`
- `backend/tests/conftest.py` — async engine, per-test session with rollback, HTTP client
- `backend/tests/test_health.py` — health + auth enforcement smoke tests

### Phase 3 — Indexing Pipeline (Week 2–3) ✅ COMPLETE
Scanner, metadata extractor, thumbnail generator, Celery tasks, file watcher.

**To deliver:**
- `app/extractors/image.py` — Pillow + exifread (width/height/orientation/GPS)
- `app/extractors/video.py` — ffprobe subprocess wrapper (duration/codec/fps/dims)
- `app/workers/tasks/scan.py` — `scan_source_task`, `process_file_task` (discovers files, dispatches per-file tasks)
- `app/workers/tasks/metadata.py` — `extract_metadata_task` (runs extractor, writes media_item)
- `app/workers/tasks/thumbnail.py` — `generate_thumbnail_task` (resumable: skip if exists)
- `app/workers/tasks/hashing.py` — `compute_hash_task` (async SHA-256, deduplication logic)
- `app/workers/tasks/watcher.py` — watchdog observer startup (fires incremental scan on FS events)
- Wire `celery_app.autodiscover_tasks` and register beat schedule

**Delivered:**
- `app/extractors/base.py` — `MediaMetadata` dataclass, `AbstractExtractor` ABC, `ExtractionError`
- `app/extractors/image.py` — Pillow + exifread; EXIF orientation correction, GPS/camera EXIF
- `app/extractors/video.py` — ffprobe subprocess wrapper; handles fps fraction strings, stream selection
- `app/workers/db.py` — `task_session()` async context manager with NullPool for prefork workers
- `app/workers/tasks/scan.py` — `scan_source_task` (walk + dispatch group), `process_file_task` (upsert + chain), `reap_stalled_jobs_task` (beat safety net)
- `app/workers/tasks/thumbnail.py` — `generate_thumbnail_task` (resumable; 2-level sharded path; image via Pillow, video via ffmpeg with 5s seek + 0s fallback)
- `app/workers/tasks/hashing.py` — `compute_hash_task` (partial SHA-256: first 1MB + size; dedup detects renames, transfers manual tags)
- `app/workers/tasks/watcher.py` — `MediaEventHandler` (watchdog), `PollingObserver` by default (WSL2 safe), lifecycle via `worker_ready`/`worker_shutdown` Celery signals
- `celery_app.py` updated — `autodiscover_tasks`, beat schedule (reap every 10 min)
- `tests/test_extractors.py` — 20 unit tests; video tests mock ffprobe subprocess

### Phase 4 — REST API (Week 3) ✅ COMPLETE

**Delivered:**
- `app/schemas/tag.py` — TagBase, TagCreate, TagUpdate, TagRef, TagResponse
- `app/schemas/media_item.py` — MediaItemSummary, MediaItemDetail, MediaItemPatch, BulkActionRequest, BulkResult
- `app/schemas/media_source.py` — SourceCreate, SourceUpdate, SourceResponse
- `app/schemas/index_job.py` — ScanRequest, JobResponse
- `app/services/storage_service.py` — get_thumbnail_path(), make_thumbnail_url()
- `app/services/media_service.py` — list/get/patch/delete/bulk + to_media_summary/detail helpers
- `app/services/search_service.py` — websearch_to_tsquery FTS + filename suggestions
- `app/services/source_service.py` — CRUD + trigger_scan() dispatches Celery task
- `app/routers/media.py` — GET/PATCH/DELETE /media, /media/{id}, /thumbnail, /stream, /bulk
- `app/routers/search.py` — GET /search, /search/suggestions
- `app/routers/tags.py` — full CRUD /tags + GET /tags/{id}/media
- `app/routers/sources.py` — full CRUD /sources + POST /sources/{id}/scan
- `app/routers/jobs.py` — GET /jobs, /jobs/{id}, DELETE /jobs/{id} (cancel)
- `app/main.py` updated — all 5 routers registered under `/api/v1`

### Phase 5 — Frontend (Week 4)
Next.js app: auth pages, media grid/list, search, media detail, source management.

### Phase 6 — Integration & Definition of Done (Week 5)
End-to-end smoke tests, Docker Compose production profile, docs.

---

## Directory Structure

```
indexxxer_v3/
│
├── backend/                         # Python FastAPI service
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app factory, lifespan hooks
│   │   ├── config.py                # Pydantic Settings (env vars)
│   │   ├── database.py              # SQLAlchemy async engine + session factory
│   │   │
│   │   ├── models/                  # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # Base, TimestampMixin
│   │   │   ├── user.py
│   │   │   ├── media_source.py
│   │   │   ├── media_item.py
│   │   │   ├── tag.py
│   │   │   ├── index_job.py
│   │   │   └── favourite.py
│   │   │
│   │   ├── schemas/                 # Pydantic request/response schemas
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── user.py
│   │   │   ├── media_item.py
│   │   │   ├── media_source.py
│   │   │   ├── tag.py
│   │   │   ├── index_job.py
│   │   │   └── search.py
│   │   │
│   │   ├── routers/                 # FastAPI APIRouter modules
│   │   │   ├── __init__.py
│   │   │   ├── media.py             # GET/PATCH/DELETE /media, /media/{id}
│   │   │   ├── search.py            # GET /search, /search/suggestions
│   │   │   ├── tags.py              # CRUD /tags
│   │   │   ├── sources.py           # CRUD /sources, POST /sources/{id}/scan
│   │   │   └── jobs.py              # GET /jobs, /jobs/{id}
│   │   │   # NOTE: no auth.py or users.py in M1 (static token, no user management)
│   │   │
│   │   ├── services/                # Business logic (not tied to HTTP)
│   │   │   ├── __init__.py
│   │   │   ├── media_service.py     # media CRUD helpers
│   │   │   ├── search_service.py    # tsvector query builder (M1), Typesense (M2)
│   │   │   ├── source_service.py    # source scanning orchestration
│   │   │   └── storage_service.py  # local thumbnail serving (M1); swap to MinIO (M4)
│   │   │
│   │   ├── workers/                 # Celery app + task definitions
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py        # Celery app, queue routing config
│   │   │   ├── tasks/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── scan.py          # scan_source_task, scan_file_task
│   │   │   │   ├── metadata.py      # extract_metadata_task
│   │   │   │   ├── thumbnail.py     # generate_thumbnail_task
│   │   │   │   └── watcher.py       # filesystem watcher startup
│   │   │   └── beat_schedule.py    # celery-beat periodic tasks
│   │   │
│   │   ├── core/                    # Cross-cutting concerns
│   │   │   ├── __init__.py
│   │   │   ├── deps.py              # FastAPI dependency injection (get_db, get_current_user)
│   │   │   ├── exceptions.py        # Custom HTTPException subclasses
│   │   │   ├── pagination.py        # Cursor/offset pagination helpers
│   │   │   └── logging.py           # structlog configuration
│   │   │
│   │   └── extractors/              # Media metadata extraction (image + video only)
│   │       ├── __init__.py
│   │       ├── base.py              # AbstractExtractor
│   │       ├── image.py             # Pillow + exifread
│   │       └── video.py             # ffprobe subprocess wrapper
│   │
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/               # Migration files
│   │
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_auth.py
│   │   ├── test_media.py
│   │   ├── test_search.py
│   │   └── test_indexing.py
│   │
│   ├── pyproject.toml               # uv-managed deps + tool config
│   ├── .env.example
│   └── Dockerfile
│
├── frontend/                        # Next.js 15 app
│   ├── src/
│   │   ├── app/                     # App Router pages
│   │   │   ├── layout.tsx           # Root layout (providers, theme)
│   │   │   ├── page.tsx             # Redirect → /library
│   │   │   ├── login/
│   │   │   │   └── page.tsx
│   │   │   ├── library/
│   │   │   │   ├── page.tsx         # Media grid/list main view
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx     # Media detail page
│   │   │   ├── sources/
│   │   │   │   └── page.tsx         # Source management
│   │   │   └── settings/
│   │   │       └── page.tsx         # User settings, appearance
│   │   │
│   │   ├── components/
│   │   │   ├── ui/                  # shadcn/ui primitives
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   ├── Topbar.tsx
│   │   │   │   └── ThemeProvider.tsx
│   │   │   ├── media/
│   │   │   │   ├── MediaGrid.tsx    # Virtualised grid
│   │   │   │   ├── MediaList.tsx    # Table-style list
│   │   │   │   ├── MediaCard.tsx    # Thumbnail + meta overlay
│   │   │   │   ├── MediaDetail.tsx  # Full detail panel/page
│   │   │   │   └── ViewToggle.tsx   # Grid/list + size controls
│   │   │   ├── search/
│   │   │   │   ├── SearchBar.tsx    # Debounced input
│   │   │   │   ├── FilterPanel.tsx  # Type, tags, date range
│   │   │   │   └── SearchResults.tsx
│   │   │   └── sources/
│   │   │       ├── SourceList.tsx
│   │   │       └── AddSourceModal.tsx
│   │   │
│   │   ├── lib/
│   │   │   ├── api/
│   │   │   │   ├── client.ts        # axios/fetch base client with auth headers
│   │   │   │   ├── media.ts
│   │   │   │   ├── search.ts
│   │   │   │   ├── sources.ts
│   │   │   │   └── auth.ts
│   │   │   ├── hooks/
│   │   │   │   ├── useMedia.ts
│   │   │   │   ├── useSearch.ts
│   │   │   │   └── useAuth.ts
│   │   │   ├── store/
│   │   │   │   └── uiStore.ts       # Zustand: viewMode, thumbnailSize, etc.
│   │   │   └── utils.ts
│   │   │
│   │   └── types/
│   │       └── api.ts               # TypeScript interfaces mirroring API schemas
│   │
│   ├── public/
│   ├── package.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── Dockerfile
│
├── infra/
│   ├── docker-compose.yml           # Full local dev stack
│   ├── docker-compose.prod.yml      # Prod overrides (resource limits, restart)
│   ├── traefik/
│   │   ├── traefik.yml
│   │   └── dynamic.yml
│   └── minio/
│       └── init-buckets.sh          # Create thumbnails/, previews/, exports/
│
├── scripts/
│   ├── seed.py                      # Create admin user + sample source
│   └── dev.sh                       # Start services shortcut
│
├── docs/
│   └── api.md                       # Hand-written API notes (Swagger auto-generated)
│
├── findings.md                      # This architecture document
├── task_plan.md                     # This file
├── progress.md                      # Session/milestone tracker
└── .gitignore
```

---

## Database Schema (M1)

```sql
-- =========================================================
-- NOTE: No users table in M1. Auth is a static API token
-- set in config. Users table added in M4 with Keycloak.
-- =========================================================

-- =========================================================
-- MEDIA SOURCES  (directories / mounts to scan)
-- =========================================================
CREATE TABLE media_sources (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    path        TEXT        NOT NULL,
    source_type VARCHAR(50) NOT NULL DEFAULT 'local',  -- local | smb | ftp (M4)
    enabled     BOOLEAN     NOT NULL DEFAULT true,
    scan_config JSONB,                   -- include/exclude globs, depth limit
    last_scan_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =========================================================
-- MEDIA ITEMS
-- =========================================================
CREATE TABLE media_items (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id       UUID        NOT NULL REFERENCES media_sources(id) ON DELETE CASCADE,

    -- File identity
    file_path       TEXT        NOT NULL,          -- absolute path on host
    filename        VARCHAR(512) NOT NULL,
    file_hash       VARCHAR(64,                    -- SHA-256 (populated async)
    file_size       BIGINT,
    file_mtime      TIMESTAMPTZ,

    -- Media classification
    media_type      VARCHAR(20),                   -- image | video
    mime_type       VARCHAR(100),

    -- Image / video dimensions
    width           INT,
    height          INT,
    duration_seconds FLOAT,                        -- null for images
    bitrate         INT,
    codec           VARCHAR(50),
    frame_rate      FLOAT,

    -- Derived assets (local filesystem paths)
    thumbnail_path  TEXT,                          -- absolute path under THUMBNAIL_ROOT
    preview_path    TEXT,                          -- WebM strip (M3)

    -- Status
    index_status    VARCHAR(30) NOT NULL DEFAULT 'pending',
    -- pending | extracting | thumbnailing | indexed | error
    index_error     TEXT,

    -- Full-text search
    search_vector   tsvector,                      -- updated by trigger

    -- Timestamps
    indexed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_source_path UNIQUE (source_id, file_path)
);

-- tsvector trigger (populated from filename + tag names)
CREATE INDEX idx_media_fts      ON media_items USING GIN (search_vector);
CREATE INDEX idx_media_type     ON media_items (media_type);
CREATE INDEX idx_media_source   ON media_items (source_id);
CREATE INDEX idx_media_status   ON media_items (index_status);
CREATE INDEX idx_media_mtime    ON media_items (file_mtime DESC);
CREATE INDEX idx_media_indexed  ON media_items (indexed_at DESC);

-- =========================================================
-- TAGS
-- =========================================================
CREATE TABLE tags (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    slug        VARCHAR(255) NOT NULL UNIQUE,      -- url-safe normalised name
    category    VARCHAR(100),                      -- performer | studio | genre | etc.
    color       VARCHAR(7),                        -- hex #rrggbb
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tags_category ON tags (category);
CREATE INDEX idx_tags_name ON tags (name);

-- =========================================================
-- MEDIA ↔ TAGS  (junction)
-- =========================================================
CREATE TABLE media_tags (
    media_id    UUID        NOT NULL REFERENCES media_items(id) ON DELETE CASCADE,
    tag_id      UUID        NOT NULL REFERENCES tags(id)        ON DELETE CASCADE,
    confidence  FLOAT       NOT NULL DEFAULT 1.0,  -- 1.0 = manual, 0.0–1.0 = AI
    source      VARCHAR(30) NOT NULL DEFAULT 'manual',  -- manual | ai | filename
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (media_id, tag_id)
);

CREATE INDEX idx_media_tags_tag ON media_tags (tag_id);

-- =========================================================
-- INDEX JOBS  (one per source scan invocation)
-- =========================================================
CREATE TABLE index_jobs (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id       UUID        NOT NULL REFERENCES media_sources(id) ON DELETE CASCADE,
    job_type        VARCHAR(30) NOT NULL DEFAULT 'full',  -- full | incremental | rehash
    status          VARCHAR(30) NOT NULL DEFAULT 'pending',
    -- pending | running | completed | failed | cancelled
    total_files     INT,
    processed_files INT         NOT NULL DEFAULT 0,
    failed_files    INT         NOT NULL DEFAULT 0,
    skipped_files   INT         NOT NULL DEFAULT 0,
    celery_task_id  VARCHAR(255),
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =========================================================
-- SAVED FILTER SETS  (M2 feature, schema defined now to avoid M2 breaking migration)
-- NOTE: No user_id FK since no users table in M1 — filters are global in M1/M2,
--       user-scoped in M4 when users are added.
-- =========================================================
CREATE TABLE saved_filters (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    filters     JSONB       NOT NULL,  -- serialised FilterSet
    is_default  BOOLEAN     NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- NOTE: favourites table deferred to M4 (requires users table).

-- =========================================================
-- SEARCH VECTOR TRIGGER
-- =========================================================
CREATE OR REPLACE FUNCTION update_media_search_vector()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', coalesce(NEW.filename, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(NEW.mime_type, '')), 'C');
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_media_search_vector
    BEFORE INSERT OR UPDATE OF filename, mime_type
    ON media_items
    FOR EACH ROW EXECUTE FUNCTION update_media_search_vector();
```

**Notes:**
- Tag names are added to `search_vector` via a separate Celery task after tagging (not inline in trigger, to avoid locking).
- `saved_filters` table defined in M1 schema so M2 doesn't need a breaking migration.
- `file_hash` is populated asynchronously by a background Celery task to avoid blocking initial indexing.
- `clip_embedding vector(768)` column added to `media_items` in M2 migration via `CREATE EXTENSION vector`.

---

## API Contract (M1)

Base URL: `http://localhost:8000/api/v1`

All endpoints require: `X-API-Token: <token>` header (or `Authorization: Bearer <token>`).
Token is set once in `.env` as `API_TOKEN`. No login flow in M1.

### Media

```
GET    /media                query: page, limit, sort, order, type, source_id, tag_ids[], status
                             → PaginatedResponse<MediaItem>

GET    /media/{id}                                               → MediaItem (full)
PATCH  /media/{id}           body: {filename?, tags?: [{id,op}]}  → MediaItem
DELETE /media/{id}           (removes index entry, not file)    → 204

GET    /media/{id}/thumbnail                                     → 200 streaming response (local file)
GET    /media/{id}/stream                                        → 200 streaming response (original file)

POST   /media/bulk           body: {ids[], action, payload}     → BulkResult
                             actions: add_tags | remove_tags | delete
```

### Search

```
GET    /search               query: q, type, tag_ids[], source_id, date_from, date_to,
                                    sort (relevance|date|size|name), order, page, limit
                             → PaginatedResponse<MediaItem> with highlights

GET    /search/suggestions   query: q, limit                    → string[]
```

### Tags

```
GET    /tags                 query: category, q, page, limit    → PaginatedResponse<Tag>
POST   /tags                 body: {name, category?, color?}    → Tag
GET    /tags/{id}                                               → Tag
PUT    /tags/{id}            body: {name?, category?, color?}   → Tag
DELETE /tags/{id}                                               → 204
GET    /tags/{id}/media      query: page, limit                 → PaginatedResponse<MediaItem>
```

### Sources

```
GET    /sources                                                  → Source[]
POST   /sources              body: {name, path, source_type?, scan_config?} → Source
GET    /sources/{id}                                            → Source
PUT    /sources/{id}         body: {name?, path?, enabled?, scan_config?}  → Source
DELETE /sources/{id}                                            → 204
POST   /sources/{id}/scan    body: {job_type: full|incremental} → IndexJob
```

### Jobs

```
GET    /jobs                 query: source_id, status, page, limit  → PaginatedResponse<IndexJob>
GET    /jobs/{id}                                                    → IndexJob
DELETE /jobs/{id}            (cancel if running)                    → 204
```

### System

```
GET    /health               (unauthenticated)                  → {status, version}
```

### Response Shapes

```typescript
// Paginated wrapper
interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

// MediaItem (summary)
interface MediaItem {
  id: string;
  source_id: string;
  filename: string;
  file_path: string;
  media_type: 'image' | 'video' | 'audio';
  mime_type: string;
  width?: number;
  height?: number;
  duration_seconds?: number;
  file_size: number;
  thumbnail_url?: string;       // /api/v1/media/{id}/thumbnail
  tags: TagRef[];
  index_status: string;
  indexed_at: string;           // ISO 8601
}

// TagRef (embedded in MediaItem)
interface TagRef {
  id: string;
  name: string;
  category?: string;
  color?: string;
  confidence: number;
  source: 'manual' | 'ai' | 'filename';
}
```

---

## Key Files to Create (Phase Order)

### Phase 1 — Infrastructure
- `infra/docker-compose.yml`
- `infra/traefik/traefik.yml`
- `infra/minio/init-buckets.sh`
- `backend/pyproject.toml`
- `backend/.env.example`
- `backend/app/config.py`
- `backend/app/main.py` (minimal, just boots)
- `backend/Dockerfile`
- `frontend/package.json`
- `frontend/Dockerfile`
- `.gitignore`

### Phase 2 — Data Layer
- `backend/app/database.py`
- `backend/app/models/base.py`
- `backend/app/models/media_source.py`
- `backend/app/models/media_item.py`
- `backend/app/models/tag.py`
- `backend/app/models/index_job.py`
- `backend/app/models/saved_filter.py`  ← stub for M2
- `backend/alembic/env.py` + initial migration
- `scripts/seed.py`

### Phase 3 — Indexing Pipeline
- `backend/app/workers/celery_app.py`
- `backend/app/workers/tasks/scan.py`
- `backend/app/workers/tasks/metadata.py`
- `backend/app/workers/tasks/thumbnail.py`
- `backend/app/workers/tasks/watcher.py`
- `backend/app/extractors/video.py`
- `backend/app/extractors/image.py`

### Phase 4 — REST API
- `backend/app/core/deps.py`
- `backend/app/core/exceptions.py`
- `backend/app/core/pagination.py`
- `backend/app/schemas/*.py` (all)
- `backend/app/services/search_service.py`
- `backend/app/services/storage_service.py`
- `backend/app/routers/media.py`
- `backend/app/routers/search.py`
- `backend/app/routers/tags.py`
- `backend/app/routers/sources.py`
- `backend/app/routers/jobs.py`

### Phase 5 — Frontend
- `frontend/src/app/layout.tsx`
- `frontend/src/app/login/page.tsx`
- `frontend/src/app/library/page.tsx`
- `frontend/src/app/library/[id]/page.tsx`
- `frontend/src/app/sources/page.tsx`
- `frontend/src/components/media/MediaGrid.tsx`
- `frontend/src/components/media/MediaCard.tsx`
- `frontend/src/components/media/MediaDetail.tsx`
- `frontend/src/components/search/SearchBar.tsx`
- `frontend/src/components/search/FilterPanel.tsx`
- `frontend/src/lib/api/client.ts`
- `frontend/src/lib/api/*.ts`
- `frontend/src/lib/store/uiStore.ts`

---

## Definition of Done — Milestone 1

All of the following must be true before M1 is considered complete:

**Infrastructure**
- [ ] `docker compose up` (from `infra/`) starts all services (PostgreSQL, Redis, backend, worker, frontend) with no manual steps beyond copying `.env.example` → `.env`
- [ ] `./data/thumbnails/` directory created automatically on first start
- [ ] `/mnt/e/media` is accessible inside backend and worker containers as `/media` (read-only)

**Auth**
- [ ] `API_TOKEN` set in `.env`; all API endpoints return 401 if token missing/wrong
- [ ] Health endpoint (`GET /health`) is unauthenticated

**Indexing**
- [ ] User can create a media source (local path) via API or UI
- [ ] Triggering a scan enqueues a Celery job visible in `GET /jobs`
- [ ] Celery worker processes files: extracts metadata, generates thumbnail, writes `media_items` rows
- [ ] Both media types (image, video) produce at minimum: filename, file_size, mime_type, media_type, and a thumbnail (video → first keyframe via ffmpeg, image → resized copy via Pillow)
- [ ] File watcher detects new files dropped into a watched source and triggers incremental indexing automatically

**Search & Browse**
- [ ] `GET /search?q=foo` returns ranked results using tsvector full-text search
- [ ] `GET /media` supports pagination, sort by date/name/size, filter by type and tag
- [ ] Tag CRUD works; tags can be assigned to media items

**Frontend**
- [ ] Library page loads, shows media grid with thumbnails (served from backend)
- [ ] Search bar filters results in real time (debounced 300ms)
- [ ] Grid/list view toggle persists in `localStorage`
- [ ] Thumbnail size slider (small/medium/large) works
- [ ] Dark mode toggle works and persists in `localStorage`
- [ ] Media detail page shows all extracted metadata and tags
- [ ] Source management page: add source (`/mnt/e/media/xxx`), trigger scan, view live job progress

**Quality**
- [ ] `pytest` passes (≥ 80% coverage on services and routers)
- [ ] No bare `except:` clauses; all errors return structured JSON `{detail: string}`
- [ ] Alembic `upgrade head` runs clean on a fresh database
- [ ] All secrets in `.env`, never hardcoded

---

## Dependencies & Versions (M1)

### Backend (`pyproject.toml`)
```toml
[project]
name = "indexxxer"
version = "0.1.0"
requires-python = ">=3.12"

dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
    "alembic>=1.13",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "celery[redis]>=5.4",
    "redis>=5.0",
    "watchdog>=4.0",
    "ffmpeg-python>=0.2",
    "Pillow>=10.4",
    "exifread>=3.0",
    "structlog>=24.1",
    "httpx>=0.27",           # async HTTP client (Ollama, Typesense later)
    "python-multipart>=0.0.9",
    "aiofiles>=23.2",
]
# Removed from M1: python-jose, passlib (no JWT auth), minio (local FS), mutagen (no audio)

[tool.uv]
dev-dependencies = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
    "factory-boy>=3.3",
    "coverage[toml]>=7",
]
```

### Frontend (`package.json`)
```json
{
  "dependencies": {
    "next": "15.x",
    "react": "19.x",
    "react-dom": "19.x",
    "@tanstack/react-query": "^5",
    "@tanstack/react-virtual": "^3",
    "zustand": "^5",
    "axios": "^1.7",
    "tailwindcss": "^4",
    "class-variance-authority": "^0.7",
    "clsx": "^2",
    "lucide-react": "^0.400",
    "next-themes": "^0.3"
  },
  "devDependencies": {
    "typescript": "^5",
    "@types/react": "^19",
    "@types/node": "^22"
  }
}
```

---

## Risk Register (M1)

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| ffprobe not available in worker container | Med | High | Pin `ffmpeg` in Dockerfile; health-check at startup |
| Large video files stall thumbnail worker | Med | Med | `ffmpeg` timeout (`-t 5` for keyframe) + Celery task `time_limit` |
| SHA-256 hashing of 3TB is slow on first scan | High | Med | Hash in background async task; file is indexed before hash completes |
| Thumbnail root not writable in container | Med | High | Docker volume declaration ensures directory exists; entrypoint `mkdir -p` |
| tsvector search quality poor for filename-only libraries | Low | Med | Planned replacement with Typesense in M2; acceptable for M1 |
| Schema design locks out M2 vector features | Low | High | `saved_filters` + `search_vector` added now; `clip_embedding` added via M2 migration |
| Celery worker crashes silently | Low | High | Celery `max_retries`, structlog, Flower UI for visibility |
| WSL2 path `/mnt/e/media` inaccessible in Docker | Med | High | Volume mount verified in compose; document required WSL2 mount config |
