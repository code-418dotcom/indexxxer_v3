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

### In Progress
- [ ] **M1 Phase 5 — Frontend** (library page, search, media detail, sources UI)

### Pending
- [ ] M1 Phase 5 — Frontend (library page, search, media detail, sources UI)
- [ ] M1 Phase 6 — Integration & DoD

---

## Milestone Tracker

| Milestone | Scope | Status | Est. Effort |
|-----------|-------|--------|-------------|
| M1 | Foundation: indexing, REST API, basic UI, auth | PLANNED | 4–5 weeks |
| M2 | Search: Typesense, semantic, filtering, better UI | PLANNED | 4 weeks |
| M3 | AI Pipeline: captions, tags, face rec, recommendations | PLANNED | 5–6 weeks |
| M4 | Platform: GraphQL, webhooks, SSO, connectors, analytics | PLANNED | 5 weeks |
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
