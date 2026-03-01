# indexxxer_v3 — Architecture Findings & Recommendations

> Planning session: 2026-03-01
> Status: DRAFT — awaiting decisions on open questions (§5)

---

## 1. Technology Stack Recommendation

### 1.1 Backend

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | **Python 3.12** | Non-negotiable for ML/AI ecosystem. asyncio-native. |
| Framework | **FastAPI** | Async-first, auto-generates OpenAPI/Swagger, dependency injection, excellent Pydantic v2 integration. Fastest Python web framework for I/O-bound workloads. |
| ORM | **SQLAlchemy 2.0** (async) | Mature, async-native in v2, pairs perfectly with Alembic for migrations. |
| Migrations | **Alembic** | Schema version control, auto-generation from models. |
| Validation | **Pydantic v2** | Built into FastAPI; fast Rust-backed validation. |

**Why not Go/Rust?** The ML pipeline (CLIP, Whisper, InsightFace) has first-class Python bindings. Maintaining a polyglot ML bridge adds complexity with no net gain. FastAPI's performance is adequate for this use case.

---

### 1.2 Database

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Primary DB | **PostgreSQL 16** | ACID, jsonb columns, full-text search via `tsvector/tsquery`, row-level security for RBAC. |
| Vector extension | **pgvector** | Adds `vector` column type + HNSW/IVFFlat indexes for semantic similarity search — eliminates a separate vector DB for M1–M2. No extra service to operate. |
| FTS approach | **PostgreSQL tsvector** (M1) → **Typesense** (M2) | pg FTS is good enough for M1 to avoid complexity. Typesense added in M2 for faceting, typo-tolerance, and sub-100ms responses at scale. |

**Why not Elasticsearch?** ES is operationally heavy (JVM, index management, cluster config). Typesense is purpose-built for product search, self-hosted, ~50 MB RAM, and far simpler to operate. pgvector means we avoid Qdrant/Pinecone for embedding storage.

---

### 1.3 Search Engine

**Choice: Typesense 0.26+**

- Typo-tolerant, faceted, vector-hybrid search in one binary
- REST API with instant synonym/filter updates (no re-indexing)
- Docker image < 100 MB
- Supports multi-search (media items + tags in one round trip)
- Mirror data from PostgreSQL via a sync worker; Typesense is query-only — PostgreSQL remains the source of truth

---

### 1.4 ML / AI Pipeline

All models run locally on the **RTX 4000 ADA (20 GB VRAM)**.

| Feature | Model / Tool | Runs Via | VRAM est. |
|---------|-------------|----------|-----------|
| Image/video embeddings | **CLIP ViT-L/14** (OpenAI) | Python `open_clip` | ~1.5 GB |
| Speech-to-text | **Whisper large-v3** | `faster-whisper` (CTranslate2) | ~3 GB |
| Auto-tagging (vision) | **BLIP-2 / LLaVA-Next** | `transformers` | ~8 GB |
| Face detection | **InsightFace (ArcFace)** | `insightface` python lib | ~1 GB |
| LLM features (summaries, NL search) | **Qwen2.5-Coder-32B** | Ollama (already running) | ~18 GB (Q4) |
| Tag suggestions | CLIP zero-shot + custom label list | same as CLIP | — |

**Note**: No audio pipeline. `mutagen` not used. Media scope is **image + video only** (decided 2026-03-01).

**GPU scheduling**: Models are not loaded simultaneously. The ML worker service manages a model registry with lazy loading and LRU eviction. Whisper + BLIP-2 can't coexist with Qwen; the worker yields to Ollama when needed.

**Embedding storage**: 768-dim CLIP vectors stored in `pgvector` with HNSW index. Cosine similarity search for semantic queries.

---

### 1.5 Frontend

**Choice: Next.js 15 (App Router) + TypeScript + Tailwind CSS 4**

| Library | Purpose |
|---------|---------|
| Next.js 15 | File-based routing, SSR for SEO, streaming, image optimisation |
| Tailwind CSS 4 | Utility-first, dark mode via `dark:` variant, theming via CSS variables |
| TanStack Query v5 | Server state, cache invalidation, optimistic updates |
| TanStack Virtual | Virtualised grid/list for 100k+ item collections |
| Zustand | Minimal client state (UI prefs, selected items) |
| shadcn/ui | Accessible component primitives, not a full library lock-in |
| React Player / Video.js | Video playback with seek-preview (WebM strips) |

**Why not SvelteKit?** Next.js has a larger ecosystem, better React-ecosystem ML/AI component support, and the team is more likely to know it.

---

### 1.6 API Layer

| Layer | Choice | When |
|-------|--------|------|
| REST | **FastAPI** (auto-OpenAPI) | M1 — all CRUD and search endpoints |
| GraphQL | **Strawberry-graphql** | M4 — adds subscription support for live indexing events |
| API Gateway | **Traefik** | M1 infra — SSL termination, routing `/api` → backend, `/` → frontend |

Strawberry is chosen over Ariadne/Graphene because it is fully type-annotated (dataclasses/Pydantic) and async-native.

---

### 1.7 Queue System

**Choice: Celery 5 + Redis (Broker) + Redis (Result Backend)**

- Celery handles CPU-bound ML tasks on dedicated workers
- Redis broker is shared with the cache layer (separate DB indexes)
- Task routing: `indexing.*` → CPU workers; `ml.*` → GPU worker; `thumbnails.*` → CPU workers
- `celery-beat` for scheduled re-indexing and health checks
- Flower for queue monitoring UI (optional, behind auth)

Alternative considered: **ARQ** (async, lighter). Rejected because Celery's task routing, retry policies, and rate-limiting are needed for the GPU worker scheduling problem.

---

### 1.8 Caching

**Choice: Redis 7**

| Use | Redis pattern |
|-----|--------------|
| API response cache (search results, tag lists) | `GET` with TTL, invalidated on write |
| Session / JWT blocklist | Hash set with TTL |
| Celery broker + result store | Separate DB index (0 = cache, 1 = celery broker, 2 = celery results) |
| Thumbnail URL presigned cache | Short TTL string |
| Rate limiting | Token bucket via `redis-py` + `lua` script |

---

### 1.9 Auth

**M1: Static API Token** _(decided 2026-03-01)_
- Single bearer token set in `.env` as `API_TOKEN`
- FastAPI dependency `require_token` validates `Authorization: Bearer <token>` or `X-API-Token: <token>` header on all routes
- No user table, no login endpoint, no session management in M1
- `python-jose` and `passlib` are not needed in M1

**M4: Keycloak + LDAP/SSO**
- Keycloak handles LDAP, SAML 2.0, OIDC
- FastAPI validates JWT issued by Keycloak (JWKS endpoint)
- Drop-in replacement — the `require_token` dependency becomes `get_current_user`

---

### 1.10 Thumbnail / Derived Asset Storage

**M1–M3: Local filesystem** _(decided 2026-03-01)_
- Thumbnails stored at `{THUMBNAIL_ROOT}/{media_id[:2]}/{media_id}.jpg` (two-level shard to stay under filesystem dir-entry limits)
- `THUMBNAIL_ROOT` defaults to `./data/thumbnails` (Docker volume)
- Served by FastAPI at `GET /api/v1/media/{id}/thumbnail` (streaming response)
- Thumbnail generation is **resumable**: worker checks for existing file before processing

**M4+: MinIO / S3 (optional)**
- MinIO can be introduced as a drop-in replacement when cloud portability is needed
- Storage abstraction lives in `services/storage_service.py` from day one; swap implementation without changing routers

Media files are **never moved** — indexed in-place. Only derived assets (thumbnails, WebM strips) are written.

---

### 1.11 Infrastructure

| Component | Local | Cloud (optional) |
|-----------|-------|-----------------|
| All services | Docker Compose | Docker Compose on VM / K8s Helm |
| Reverse proxy | Traefik | Same |
| Monitoring | Prometheus + Grafana | Same |
| Logging | Loki + Promtail (Grafana stack) | Same |
| CI/CD | GitHub Actions | GitHub Actions |

**Everything can run locally** on a single machine given the RTX 4000 ADA and reasonable RAM (recommend ≥ 32 GB system RAM for full stack).

---

## 2. System Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                        Client (Browser)                         │
│                     Next.js 15 (SSR + CSR)                     │
└─────────────────────────────┬──────────────────────────────────┘
                              │ HTTPS
┌─────────────────────────────▼──────────────────────────────────┐
│                     Traefik (Reverse Proxy)                     │
│              SSL termination · routing · rate limit             │
└──────┬──────────────────────────────────────┬──────────────────┘
       │ /api/*                                │ /*
┌──────▼──────────────────┐          ┌─────────▼──────────┐
│   FastAPI Backend        │          │  Next.js Frontend  │
│   REST (M1) + GQL (M4)  │          │  (static export or │
│   Pydantic · SQLAlchemy  │          │   Node SSR)        │
└──────┬──────┬───────────┘          └────────────────────┘
       │      │
       │      │ async tasks
       │  ┌───▼────────────────────┐
       │  │   Redis                │
       │  │   DB0: API cache       │
       │  │   DB1: Celery broker   │
       │  │   DB2: Celery results  │
       │  └───┬────────────────────┘
       │      │
       │  ┌───▼────────────────────────────────────────────┐
       │  │   Celery Workers                                │
       │  │                                                 │
       │  │  [CPU Pool]           [GPU Worker]              │
       │  │  - filesystem scan    - CLIP embeddings         │
       │  │  - metadata extract   - Whisper STT             │
       │  │  - ffmpeg thumbs      - BLIP-2 auto-tag         │
       │  │  - Typesense sync     - InsightFace             │
       │  │  - export/import      - Ollama LLM tasks        │
       │  └───────────────────────────────────────────────┘
       │
       │ SQLAlchemy (async)
┌──────▼─────────────────────────────────────────┐
│              PostgreSQL 16                       │
│   media_items · tags · users · sources · jobs    │
│   tsvector FTS index (M1)                        │
│   pgvector HNSW index on clip_embedding (M2)     │
└──────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│   Typesense (M2+)                                │
│   Mirror of media_items for faceted/fuzzy search │
│   Sync'd by Celery worker on write               │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│   MinIO                                          │
│   Buckets: thumbnails/ · previews/ · exports/    │
│   Served via presigned URLs (15 min TTL)         │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│   Ollama (already running, local)                │
│   Qwen2.5-Coder-32B                              │
│   HTTP API on :11434                             │
└─────────────────────────────────────────────────┘
```

### 2.1 Data Flow: Indexing a New File

```
1. Filesystem Watcher (watchdog) detects new/changed file
2. Publishes task → Redis (Celery broker)
3. CPU Worker: extract metadata (ffprobe/Pillow) → write media_item row (status=pending)
4. CPU Worker: generate thumbnail + WebM preview strip → upload to MinIO
5. CPU Worker: update media_item thumbnail_path, sync to Typesense
6. GPU Worker: run CLIP → store embedding in pgvector
7. GPU Worker (M2+): run BLIP-2 auto-tag → write media_tags rows
8. GPU Worker (M3+): run Whisper STT if video → store transcript
9. media_item status → 'indexed'
10. WebSocket event pushed to connected frontend clients
```

### 2.2 Data Flow: Search Query

```
1. User types query in UI
2. Frontend debounces 200ms → GET /api/v1/search?q=...
3. FastAPI checks Redis cache (TTL 60s for identical queries)
4. MISS:
   - Full-text: Typesense multi-search (M2) / pg tsvector (M1)
   - Semantic: pgvector cosine similarity on CLIP embedding of query text
   - Merge + re-rank results
5. Return paginated response, store in Redis cache
6. HIT: return cached response directly
```

### 2.3 Local vs Cloud

| Component | Runs locally | Cloud needed for |
|-----------|-------------|-----------------|
| All application services | Yes, Docker Compose | — |
| PostgreSQL + pgvector | Yes | RDS (scale) |
| Redis | Yes | ElastiCache (scale) |
| Typesense | Yes | Managed or self-hosted VM |
| Celery CPU workers | Yes | More VMs for parallel indexing |
| GPU worker (CLIP, Whisper, etc.) | Yes, RTX 4000 ADA | GPU cloud for multi-node |
| Ollama / Qwen | Yes, already running | — |
| MinIO | Yes | S3 / Backblaze B2 |
| Traefik | Yes | Same config |
| Frontend | Yes, Next.js dev server | Vercel / CDN (optional) |

---

## 3. Feature Prioritisation — Milestone Breakdown

### Milestone 1 — Foundation (Est: 4–5 weeks)
> Goal: a working, deployable system that can scan a directory, index files, and let users search and browse them.

| Feature | Category |
|---------|---------|
| Filesystem scanner (local paths) | CORE |
| Metadata extraction (ffprobe, Pillow, mutagen) | CORE |
| PostgreSQL schema (media, tags, users, sources, jobs) | CORE |
| FastAPI REST endpoints (CRUD + basic search) | CORE |
| Full-text search via pg tsvector | CORE SEARCH |
| JWT auth (admin/editor/viewer roles) | SECURITY |
| Thumbnail generation (images + video keyframes) | MEDIA |
| Celery + Redis queue for indexing jobs | PERFORMANCE |
| Incremental file watcher (watchdog) | PERFORMANCE |
| Basic responsive UI: grid/list, search bar, filters | UI/UX |
| Grid/list view toggle, adjustable thumbnail sizes | UI/UX |
| Dark mode + basic theme | UI/UX |
| Docker Compose local dev stack | INFRA |
| Alembic migrations | INFRA |

**Definition of Done**: A user can point the system at a folder, trigger a scan, wait for indexing to complete, search and filter results, and view media details — all via the web UI, authenticated.

---

### Milestone 2 — Search & Discovery (Est: 4 weeks)
> Goal: production-quality search with semantic understanding.

| Feature | Category |
|---------|---------|
| Typesense integration + pg→Typesense sync worker | SEARCH |
| CLIP embeddings + pgvector HNSW index | SEARCH |
| Semantic / natural language search | CORE SEARCH |
| Fuzzy search, typo tolerance | CORE SEARCH |
| Advanced multi-criteria filtering (UI + API) | CORE SEARCH |
| Saved filter sets (per-user) | CORE SEARCH |
| Index history + incremental re-indexing | CORE SEARCH |
| Progressive loading / infinite scroll | UI/UX |
| Keyboard shortcuts | UI/UX |
| Search analytics (query logs) | ANALYTICS |
| Personal favourites and bookmarks | SECURITY |
| CSV/JSON export | EXPORT |

---

### Milestone 3 — AI Pipeline (Est: 5–6 weeks)
> Goal: AI-powered media understanding and enrichment.

| Feature | Category |
|---------|---------|
| Automated tag suggestions (BLIP-2 / CLIP zero-shot) | AI + MEDIA |
| Auto-caption generation (LLaVA-Next or BLIP-2) | AI |
| Speech-to-text transcription (Whisper large-v3) | AI |
| Face detection + recognition (InsightFace) | MEDIA |
| Face deduplication across library | MEDIA |
| Video thumbnails (keyframe grid) | MEDIA |
| Fast-scrubbing WebM preview strips (ffmpeg) | MEDIA |
| Contextual performer/entity summaries via Ollama | AI |
| Smart recommendations (similar items) | AI |
| Bulk tagging and editing | MEDIA |
| Media relationship graph (faces, scenes, topics) | MEDIA |

---

### Milestone 4 — Platform & Integrations (Est: 5 weeks)
> Goal: API-first platform with external system integration.

| Feature | Category |
|---------|---------|
| GraphQL API (Strawberry) | API |
| Webhooks + event system | API |
| LDAP/SSO via Keycloak (OIDC) | SECURITY |
| User accounts, profiles, roles management UI | SECURITY |
| NAS/SMB media source connector | INTEGRATION |
| FTP media source connector | INTEGRATION |
| REST/GraphQL SDK (TypeScript + Python) | DEVELOPER |
| CLI tool (`ixr` command) | DEVELOPER |
| Index quality reports | ANALYTICS |
| Usage analytics dashboard | ANALYTICS |
| Backup and restore index | EXPORT |

---

### Milestone 5 — Scale & Polish (Ongoing)
> Goal: production hardening, extensibility, performance at 1M+ files.

| Feature | Category |
|---------|---------|
| Distributed queue-based indexing (multiple workers) | PERFORMANCE |
| Plugin system for custom parsers and media sources | DEVELOPER |
| Server-side caching tuning (Redis cluster) | PERFORMANCE |
| Prometheus + Grafana observability stack | INFRA |
| E2E test suite | INFRA |
| Kubernetes Helm chart | INFRA |
| Mobile-optimised responsive layout polish | UI/UX |
| Animated GIF preview generation | MEDIA |

---

## 4. Effort Summary

| Milestone | Weeks | Deployable? | Primary Risk |
|-----------|-------|-------------|-------------|
| M1 | 4–5 | Yes | Schema design needs to be future-proof |
| M2 | 4 | Yes | Typesense sync correctness; embedding quality |
| M3 | 5–6 | Yes | GPU VRAM scheduling; model quality vs speed |
| M4 | 5 | Yes | Keycloak complexity; SMB connector edge cases |
| M5 | Ongoing | Yes (incremental) | Distributed worker correctness |

---

## 5. Open Questions — Decisions Required Before Implementation

These must be resolved before M1 development starts:

### Q1: Media types in scope
Will indexxxer_v3 handle **images only**, **video only**, or **all three** (image + video + audio) from day one? This affects the metadata schema, thumbnail pipeline, and ffprobe configuration.

**Options:**
- a) All three (image + video + audio) — full schema upfront, more complex M1
- b) Image + video only — reasonable scope, audio treated as metadata-only
- c) Video-first — simplest M1, images trivial to add in M2

### Q2: File identity strategy
When a file is **moved or renamed**, should the system:
- a) Treat it as a new file (simple, loses history/tags)
- b) Detect by content hash (SHA256) — preserves tags but requires hashing every file on scan (slow for large libraries)
- c) Inode + device ID tracking (Linux-only, fast, breaks on copy)

Recommendation: **(b) hash-based identity** with async hashing in the background.

### Q3: Thumbnail storage location
Where should generated thumbnails/previews be stored?
- a) **MinIO** (S3-compatible, clean separation, extra service) — recommended
- b) **Local filesystem** alongside media (simpler, but not portable)
- c) **PostgreSQL bytea / LFS** — not recommended for performance

### Q4: Multi-user vs single-user
Is M1 intended to be **multi-user** (login page, user management) or **single-user / personal** (auth token in config, no user table)?

This affects whether the `users` table, roles, and login UI are M1 scope or can be deferred.

### Q5: Frontend deployment model
- a) **Next.js Node.js server** (SSR, full features, slightly heavier)
- b) **Static export** (`next export`, hosted by Nginx/Traefik, no server) — simpler ops
- c) **Separate frontend port** (front: 3000, API: 8000) during dev, proxied by Traefik in prod

### Q6: Index scope — hidden files and symlinks
Should the scanner follow **symlinks** and index **hidden files/directories** (dot-prefixed)? This matters for NAS mounts and media library layouts.

### Q7: Duplicate detection scope
Exact-duplicate detection (same hash) is straightforward. Should **near-duplicate detection** (perceptual hash / CLIP similarity) be in M1 or M3?

### Q8: Minimum viable UI for M1
What is the acceptable quality bar for the M1 frontend?
- a) Functional but rough (no design polish — ship logic first)
- b) Basic design polish expected (theming, dark mode, layout)
- c) Full responsive design from day one

### Q9: Naming / branding in the codebase
- Python package name: `indexxxer` or `ixr`?
- API prefix: `/api/v1/` (versioned from day one) or `/api/`?
- Port assignments: confirm defaults (API: 8000, Frontend: 3000, PostgreSQL: 5432, Redis: 6379, Typesense: 8108, MinIO: 9000/9001)?

### Q10: Existing media library characteristics
- Approximate file count (100s, 10k, 100k, 1M+)?
- Primary storage: local disk, NAS (SMB), other?
- Any existing metadata or naming conventions to preserve/parse?

---

*Answers to these questions will be recorded in `progress.md` under Decision Log and will directly inform the M1 schema, directory structure, and scaffolding priorities.*

---

## 6. Gemini Consultation — FastAPI Health Check

> Query: "What is the best community skill for a Python FastAPI health check?"
> Date: 2026-03-01

**Gemini's exact answer:**

```
[*] Consulting Strategic Manager (Cache: cachedContents/7lav8p3zzf7af2tstd7h3qsqz6dskk69vzfnpup4)...

[GEMINI STRATEGY]:
Understood. As Strategic Manager for indexxxer_v3, my first step is to thoroughly review the project plan and establish our "working memory on disk" by creating the essential planning files.

I have read and internalized `task_plan.md`. The project has successfully completed Phase 3 (Indexing Pipeline), and the next objective is **Phase 4: REST API**.

I will now create the planning files in the project root to track our progress, findings, and decisions, adhering to the Manus context engineering principles.
```
