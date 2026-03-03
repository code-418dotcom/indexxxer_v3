# indexxxer_v3 — Planning Session Progress

## Session: Architecture & Planning (2026-03-01)
Status: IN PROGRESS

### Completed
- [x] Created plan files (task_plan.md, findings.md, progress.md)
- [x] Technology stack analysis and recommendation
- [x] System architecture design
- [x] Feature prioritisation into milestones M1–M5
- [x] Milestone 1 detailed implementation plan
- [x] Open questions answered (see Decision Log below)
- [x] Plan docs updated with all decisions
- [x] **M1 Phase 1 — Infrastructure & Skeleton** (2026-03-01)
  - `.gitignore`, `.env.example`
  - `backend/`: pyproject.toml, Dockerfile, main.py, config.py, database.py, core/, all ORM models, alembic env
  - `infra/docker-compose.yml`
  - `frontend/`: package.json, next.config.ts, tsconfig.json, Tailwind v4, minimal app shell + ThemeProvider
  - `scripts/dev.sh`

- [x] **M1 Phase 2 — Data Layer** (2026-03-01)
  - FK constraints fixed in MediaItem, IndexJob, MediaTag models
  - `alembic/versions/0001_initial_schema.py` — all tables, tsvector trigger, GIN index
  - `scripts/seed.py` — idempotent seed for default media source
  - `tests/conftest.py` + `tests/test_health.py` — async fixtures + smoke tests
  - All Python files syntax-validated ✓

- [x] **M1 Phase 3 — Indexing Pipeline** (2026-03-01)
  - `extractors/`: base, image (Pillow+exifread), video (ffprobe)
  - `workers/db.py`: NullPool task session
  - `workers/tasks/scan.py`: scan_source_task, process_file_task, reap_stalled_jobs_task
  - `workers/tasks/thumbnail.py`: resumable, sharded path, image+video, ffmpeg 5s-seek fallback
  - `workers/tasks/hashing.py`: partial SHA-256 (1MB+size), rename/dedup detection
  - `workers/tasks/watcher.py`: PollingObserver (WSL2 safe), Celery lifecycle signals
  - `celery_app.py` wired: autodiscover, beat schedule
  - `tests/test_extractors.py`: 20 unit tests, ffprobe mocked
  - All 36 Python files syntax-validated ✓

- [x] **M1 Phase 4 — REST API** (2026-03-01)
  - `schemas/`: tag.py, media_item.py, media_source.py, index_job.py
  - `services/`: storage_service.py, media_service.py, search_service.py, source_service.py
  - `routers/`: media.py, search.py, tags.py, sources.py, jobs.py
  - `main.py` updated — all 5 routers registered under `/api/v1`
  - All 14 Phase 4 Python files syntax-validated ✓

- [x] **M1 Phase 5 — Frontend** (2026-03-02)
  - Library page: grid/list toggle, pagination, search + filter panel, detail side-panel ✅
  - Media detail page (`/library/[id]`) with video player, metadata, tags ✅
  - Sources page: add source, incremental/full scan, enable/disable, delete ✅
  - Logs page: live SSE job tail, progress bar, cancel job ✅
  - Settings page: API token (localStorage), backend health check ✅
  - All API clients: media, search, tags, sources, jobs ✅
  - `useJobStream` hook + `uiStore` (Zustand persist) ✅
  - Backend: `stream.py` SSE router + `workers/events.py` Redis stream emitter ✅

- [x] **M1 Phase 6 — Integration & DoD** (2026-03-02)
  - Fixed `uiStore` `partialState` → `partialize` (Zustand API)
  - Added Celery `beat` service to docker-compose.yml
  - Fixed `TagRef` schema missing `slug` field (backend + `_build_tag_refs`)
  - Added API test suite: test_media, test_tags, test_sources, test_jobs, test_search

- [x] **M2 — Search & Discovery** (2026-03-02)
  - Phase 1: `alembic/versions/0002_m2_search.py` — pgvector + pg_trgm extensions, clip_embedding vector(768), clip_status, is_favourite, HNSW index, tsvector trigger fix + backfill
  - Phase 2: `services/search_service.py` — fuzzy_text_search (pg_trgm fallback), semantic_search (CLIP), hybrid (RRF), auto-detect (≥3 words → semantic), mode param
  - Phase 3: `Dockerfile.ml` (CUDA 12.4 GPU image), `docker-compose gpu_worker + clip_models volume`, `celery_app.py` ml queue, `app/ml/clip_model.py` (ViT-L-14 singleton), `workers/tasks/clip.py` (compute + backfill tasks)
  - Phase 4: `GET /media/{id}/similar` (CLIP cosine), `GET/POST/PUT/DELETE /filters`, `GET /export?format=csv|json`, `PATCH /media` + `is_favourite`, `GET /media?favourite=true`
  - Phase 5: types (is_favourite, clip_status, SavedFilter, SearchMode), `lib/api/filters.ts`, `hooks/useInfiniteScroll.ts`, MediaCard (heart icon), MediaDetail (similar strip), SearchBar (semantic badge), SavedFilters, Sidebar (favourites nav), library/page.tsx (infinite scroll, keyboard shortcuts)
  - Phase 6: `test_search_m2.py`, `test_filters.py`, `test_export.py`

- [x] **M3 — AI Pipeline** (2026-03-02)
  - Phase 1: `alembic/versions/0003_m3_ai.py` — caption/transcript/summary columns + statuses, `media_faces` table (pgvector 512-dim, HNSW), tsvector trigger extended to include caption+transcript at weight B
  - Phase 2: `app/ml/registry.py` (LRU ModelRegistry singleton), `blip2_model.py` (BLIP-2 OPT-2.7B fp16), `whisper_model.py` (faster-whisper large-v3, ffmpeg audio extract), `insightface_model.py` (buffalo_l ArcFace 512-dim), `ollama_client.py` (async httpx, qwen2.5-coder:32b)
  - Phase 3: `workers/tasks/ai.py` — compute_caption_task, compute_transcript_task, detect_faces_task (all on `ml` queue), compute_summary_task, cluster_faces_task, backfill_ai_task (on `ai` queue); scan.py wired to dispatch AI tasks post-index; celery_app.py updated (routes + beat schedule); Dockerfile.ml (+libgomp1); pyproject.toml ml extras (faster-whisper, insightface, transformers, accelerate, onnxruntime-gpu, opencv-python-headless); docker-compose.yml (hf_models volume, worker adds `ai` queue); config.py (ollama_url, ollama_model, whisper_max_duration); .env.example updated
  - Phase 4: `models/media_face.py`, `models/__init__.py` updated, `models/media_item.py` (new M3 columns + faces relationship), `schemas/media_item.py` (summary: caption/statuses/face_count; detail: transcript/summary), `schemas/face.py`, `routers/faces.py` (GET /faces/clusters, GET /faces/clusters/{id}, GET /media/{id}/faces), `services/face_service.py`, `services/media_service.py` (WITH_TAGS_AND_FACES, M3 fields in to_media_summary/detail), `main.py` (faces router registered)
  - Phase 5: `types/api.ts` (AiStatus, M3 fields on MediaItem, Face/FaceCluster types), `lib/api/faces.ts`, `components/media/MediaDetail.tsx` (caption/transcript/summary/AI-status sections), `components/media/MediaCard.tsx` (face count badge), `app/faces/page.tsx` (cluster grid browser), `components/layout/Sidebar.tsx` (Faces nav link)

- [x] **M4 — Platform** (2026-03-03)
  - Phase 1 Auth: `alembic/versions/0004_m4_auth.py` — users table + saved_filters.user_id FK; `models/user.py`; `core/security.py` (HS256 JWT, bcrypt); `schemas/user.py`; `services/user_service.py`; `routers/auth.py` (login/refresh/logout/me); `routers/users.py` (admin CRUD); `core/deps.py` updated (get_current_user returns User, require_admin, static token backward compat); `core/redis_pool.py`; `routers/stream.py` JWT support; `.env.example` M4 vars
  - Phase 2 Connectors: `alembic/versions/0005_m4_connectors.py` — source_credentials table; `core/encryption.py` (Fernet); `models/source_credential.py`; `connectors/` (base, local, smb, ftp, factory); `schemas/credential.py`; `routers/sources.py` + credentials endpoints; `services/source_service.py` credential CRUD; `workers/tasks/scan.py` connector-based scan
  - Phase 3 Webhooks: `alembic/versions/0006_m4_webhooks.py` — webhooks + deliveries tables; `models/webhook.py`; `schemas/webhook.py`; `services/webhook_service.py`; `routers/webhooks.py` (CRUD + test endpoint); `workers/tasks/webhook.py` (HMAC delivery + retry); `workers/events.py` (emit_webhook_event async); scan.py webhook hooks
  - Phase 4 Analytics: `alembic/versions/0007_m4_analytics.py` — query_logs table; `models/query_log.py`; `workers/tasks/analytics.py`; `services/analytics_service.py`; `routers/analytics.py` (overview/queries/indexing); `routers/search.py` query logging
  - Phase 5 GraphQL: `graphql/` (types, resolvers, schema with GraphiQL); strawberry-graphql[fastapi]; mounted at /api/v1/graphql
  - Phase 6 Frontend: login page, admin layout, admin/users, admin/webhooks, admin/analytics; updated client.ts (JWT + refresh interceptor); auth.ts, users.ts, webhooks.ts, analytics.ts API modules; useCurrentUser hook; Sidebar with admin nav + logout; M4 types in api.ts
  - Phase 7 Tests: test_auth.py, test_connectors.py, test_webhooks.py, test_analytics.py, test_graphql.py; updated conftest.py for JWT

### In Progress
- Nothing — M4 COMPLETE

### Pending
- [ ] M5 — Scale: distributed workers, plugin system, K8s, Keycloak SSO

---

## Milestone Tracker

| Milestone | Scope | Status | Est. Effort |
|-----------|-------|--------|-------------|
| M1 | Foundation: indexing, REST API, basic UI, auth | COMPLETE | 4–5 weeks |
| M2 | Search: CLIP semantic, pg_trgm fuzzy, filters, export, favourites, infinite scroll | COMPLETE | 4 weeks |
| M3 | AI Pipeline: captions, tags, face rec, recommendations | COMPLETE | 5–6 weeks |
| M4 | Platform: GraphQL, webhooks, connectors, analytics | COMPLETE | 5 weeks |
| M5 | Scale & Polish: distributed workers, plugin system, CLI/SDK | PLANNED | ongoing |

---

## Decision Log

| # | Question | Decision | Date |
|---|----------|----------|------|
| Q1 | Media types in scope | **Images + video only.** No audio pipeline, no mutagen. | 2026-03-01 |
| Q2 | File identity strategy | **SHA-256 hash-based.** Survives renames/moves. Hash computed async post-scan. | 2026-03-01 |
| Q3 | Thumbnail storage | **Local filesystem** at `./data/thumbnails`. No MinIO in M1–M3. | 2026-03-01 |
| Q4 | Multi-user vs single-user | **Single-user, static API token** in config. Full auth (JWT + LDAP) deferred to M4. | 2026-03-01 |
| Q5 | Frontend deployment model | Next.js dev server on :3000 with `/api` proxy rewrites to backend :8000. | 2026-03-01 |
| Q6 | Hidden files / symlinks | Not answered — defaulting to skip hidden files, no symlink follow. Revisit if needed. | 2026-03-01 |
| Q7 | Near-duplicate detection | Deferred to M3. M1 has exact-hash deduplication only. | 2026-03-01 |
| Q8 | M1 UI quality bar | Not answered — defaulting to functional with basic dark mode. | 2026-03-01 |
| Q9 | Naming / ports | Package: `indexxxer`. API prefix: `/api/v1`. Ports: API=8000, Frontend=3000, PG=5432, Redis=6379. No MinIO in M1. | 2026-03-01 |
| Q10 | Library characteristics | ~11,000 files, ~3TB, video-heavy. Path: `/mnt/e/media/xxx`. Local disk, WSL2. | 2026-03-01 |
