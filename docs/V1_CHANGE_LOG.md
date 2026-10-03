# V1 change log: deviations from the frozen design and plans

The system design (`CivicConnect_v2_V1_System_Design.md`), the implementation plans, `TEAM_INTEGRATION_RULES.md` and `ai/inference/**` are frozen sources of truth. They may be changed when necessary, but **every deviation gets an entry here**: date, what, why. Newest entries go at the bottom. In a merge conflict on this file keep both entries.

Entry format: `## YYYY-MM-DD · short title`, then **What**, **Why**, **Affects**.

---

## 2026-10-03 · Citizen and field-worker apps are Expo, not a PWA

**What:** The citizen app and the field-worker app are built with Expo (React Native). The design's "V1 citizen frontend is a mobile-first PWA, not a separate native application" (section 63 and the PWA/IndexedDB/service-worker offline design in 63.4) no longer applies to these two apps. The admin and overlooker apps stay web apps.
**Why:** Team decision of 2026-10-03. The rationale was not recorded when the decision was relayed; whoever owns the decision should add it here.
**Affects:** Frontend plans and offline design (IndexedDB + service worker becomes on-device storage in Expo). Backend contract: the offline sync API (`/sync/mutations`, `/sync/changes`) is unchanged and still the offline path; web push (section 53) will need an equivalent for Expo push delivery, which is not decided or implemented yet. `apps/` is outside our ownership; only tiny agreed contract fixes are made from the backend side.

## 2026-10-03 · Backend ownership moved from Parth to Tanuj

**What:** Tanuj (with Claude Code sessions) now owns `backend/`, `ai/`, `alembic/`, `infra/` and `packages/api-client` entirely and may change any file in them, including frozen docs, when needed. Parth moved to the frontend; `apps/` and the other `packages/*` belong to Krrish, Vedant and Parth.
**Why:** Parth confirmed there is no unpushed backend work and moved to frontend. The backend in the repo was a scaffold and was rewritten and implemented under `docs/BACKEND_AUDIT.md`, so a single owner avoids conflicting edits.
**Affects:** `docs/IMPLEMENTATION_PLAN_PARTH.md` and `docs/TEAM_INTEGRATION_RULES.md` assign the backend to Parth and the coordination rule "agree with Parth before editing `backend/`" no longer applies. Those two documents were not edited; this entry supersedes them on ownership. Working rules: `CLAUDE.md`.

## 2026-10-03 · Python and database versions actually used versus design sections 27 and 28

**What:** The development stack differs from the version table in the design. Versions below were read from the running environment (`pip`, `SELECT version()`, `postgis_version()`), not from the design:

| Item | Design (section 27/28) | Actually used |
|---|---|---|
| Python | 3.14.x | 3.13.6 (venv `.venv`; project requires `>=3.11`) |
| PostgreSQL | 18.6 | 16.4 (Docker `postgis/postgis:16-3.4`) |
| PostGIS | 3.6.x | 3.4 |
| pgvector | 0.8.6 | not installed (embeddings stored as JSON in `case_embeddings`) |
| Redis | 8.10.x | `redis:7` image (redis-py client 8.1.0) |
| FastAPI | 0.142.2 | 0.142.2 (matches) |
| SQLAlchemy | 2.0.54 | 2.1.3 (requirements are unpinned: `sqlalchemy>=2.0.0`) |
| Alembic | 1.16.x | 1.20.0 |
| PostgreSQL driver | asyncpg (async) | psycopg2-binary (sync) |
| PyTorch (ML track, not in design) | n/a | 2.11.0+cu128 |

**Why:** The handoff's run commands use `postgis/postgis:16-3.4` and `redis:7`; Python 3.13.6 is what is installed on the development laptop; dependencies were installed unpinned and resolved to the latest releases. Migrations 0001/0002 and the demo seed ran green on PostgreSQL 16.4 + PostGIS 3.4; the 3 PostgreSQL/PostGIS integration tests pass on it (`TEST_DATABASE_URL` against the container).
**Affects:** Nothing in the API contract. Not verified against PostgreSQL 18 / PostGIS 3.6 / Python 3.14 (a PostgreSQL 18 service also runs on this laptop but PostGIS availability there was not checked). Pin versions in `backend/requirements.txt` and re-test on the target versions before a real deployment. Local note: a host PostgreSQL service owns port 5432, so the PostGIS container is published on 5433.

## 2026-10-04 · Database image is now PostgreSQL 18.6 + PostGIS 3.6 + pgvector 0.8.6 (supersedes the database rows of the 2026-10-03 versions entry)

**What:** The development database is built from `infra/docker/postgres/Dockerfile` (`postgis/postgis:18-3.6` plus `postgresql-18-pgvector`) and started by `scripts/dev/db_up.ps1` as container `civic-db` on host port 5433 with the named volume `civic-pgdata`. Versions read from the running container:

| Item | Design (section 28) | Actually used |
|---|---|---|
| PostgreSQL | 18.6 | 18.6 (Debian 18.6-1.pgdg13+2, Debian 13 trixie) |
| PostGIS | 3.6.x | 3.6 (`postgis_version()` = `3.6 USE_GEOS=1 USE_PROJ=1 USE_STATS=1`) |
| pgvector | 0.8.6 | 0.8.6 (`CREATE EXTENSION vector` works; no table uses it yet, embeddings are still JSON) |
| Redis | 8.10.x | 7.4.11 (`redis:7` image; design not met, no Redis 8 feature is used) |

Still different from the design: Python 3.13.6 (design 3.14.x), SQLAlchemy 2.1.3 (2.0.54), Alembic 1.20.0 (1.16.x), psycopg2 sync driver (asyncpg), redis-py 8.1.0.
**Why:** The 18-3.6 tag exists, so the design versions were used. Verified on it: `alembic upgrade head` (0001, 0002), `alembic check` (no drift), `seed_demo` (560 cases), and the 3 PostgreSQL/PostGIS integration tests (`TEST_DATABASE_URL`) all pass, so the 16-3.4 fallback was not needed.
**Affects:** The PostgreSQL 18 image keeps PGDATA under `/var/lib/postgresql/<major>/docker`, so the data volume is mounted at `/var/lib/postgresql` (not `/data`). A volume created by a 16.x container cannot be reused by 18 (use `db_up.ps1 -ResetData` or another volume name). No API contract change. Frozen documents and `ai/inference/**` were not edited in this step.

## 2026-10-04 · OTP / email login deferred; password authentication stays (design §41)

**What:** OTP login (design §41) is not built in V1. Login stays identifier + password (bcrypt, access JWT + rotating refresh token), as already implemented in `backend/api/v1/auth.py`. The `/auth/*` contract of §51A.2 is unchanged.
**Why:** OTP needs an SMS or email delivery provider, and no free one is available to this project (everything must stay free).
**Affects:** Citizen onboarding is password-based; no OTP tables or endpoints exist. Revisit only if a free delivery channel is found; the `device_tokens` table added by migration 0003 is for Expo push notifications, not for OTP.

## 2026-10-04 · pgvector uses an untyped-dimension column (migration 0003)

**What:** `case_embeddings` gets `embedding_vec vector` **without a fixed dimension**, plus `embedding_dim` and `embedding_model`. Similarity search uses two partial HNSW cosine expression indexes, one for 384 and one for 768 dimensions: `CREATE INDEX ix_case_embeddings_vec_<dim> ON case_embeddings USING hnsw ((embedding_vec::vector(<dim>)) vector_cosine_ops) WHERE (embedding_dim = <dim>)` (the pattern of the pgvector README, "Can I store vectors with different dimensions in the same column?"). A query must repeat the predicate and the cast to use an index: `WHERE embedding_dim = 384 ORDER BY embedding_vec::vector(384) <=> CAST(:q AS vector(384))`. The JSON `vector` column stays (it is what SQLite and servers without pgvector use). Design section 28 lists pgvector 0.8.6 without a column definition; this adds one.
**Why:** The final embedding dimension depends on whether multilingual-e5-small (384) or multilingual-e5-base (768) wins the M6/M7 evaluation, and that is not decided yet. A fixed `vector(384)` column would force a migration of every embedding later; the untyped column plus one partial index per candidate dimension needs none. An index for the losing dimension can be dropped afterwards.
**Affects:** The column and its indexes are PostgreSQL-only and are not mapped in the ORM (like `civic_cases.geog`): `alembic/env.py` ignores them, they are read and written with SQL. Verified on PostgreSQL 18.6 + pgvector 0.8.6: 384- and 768-dim vectors coexist, the 384 query uses `ix_case_embeddings_vec_384`, upgrade / downgrade -1 / upgrade and `alembic check` (no drift) pass. If the extension is not available (`pg_available_extensions`) or cannot be created, 0003 adds only `embedding_dim` and `embedding_model`, logs a warning, and `GET /api/v1/health/ready` reports `"vector_search": false` (verified on PostgreSQL 16.4 without pgvector); readiness is unaffected. `vector_search` is a new additive field of that response.

## 2026-10-04 · Migration 0003 and the schema it adds; migration 0001 made SQLite-portable

**What:** Migration 0003 (down_revision 0002) adds `system_settings`, `device_tokens` (Expo push tokens), `case_flags` (STILL_EXISTS / OUTDATED / INCORRECT / INAPPROPRIATE, unique per case+user+kind), `evidence_items.scan_*` (malware scan state, design §44; new rows PENDING, rows that existed before 0003 UNSCANNED), `notifications.push_*` (Expo delivery state, §53) and the pgvector columns above. Migration 0001 was edited: the two circular foreign keys (`wards.officer_id`, `evidence_items.work_order_id`) are now added and dropped with `batch_alter_table` instead of `create_foreign_key` / `drop_constraint`. `backend/scripts/generate_openapi.py` now writes LF on every OS.
**Why:** The task requires `alembic upgrade head` / `downgrade -1` / `upgrade head` to work on SQLite as well as PostgreSQL, and `upgrade head` on SQLite had never worked (0001 failed with "No support for ALTER of constraints in SQLite"); only `create_all` was used there. Batch mode emits the same `ALTER TABLE` on PostgreSQL, so databases already migrated to 0001/0002 are unaffected (the demo database was upgraded 0002 to 0003 in place). Check constraints on the allowed values exist only for the new table `case_flags`; on the altered tables (`scan_status`, `push_status`) SQLite cannot add them without recreating the table, so those values are enforced by the application (`SCAN_STATUSES`, `PUSH_STATUSES` in `backend.models`).
**Affects:** Only the schema step adds Alembic revisions until the final prompt (CLAUDE.md). No existing API response changed apart from `vector_search` on the readiness endpoint. The API surface for the new tables (device registration, flags, settings, scan worker, Expo push) is built by later lanes; `backend/schemas/platform.py` holds their request/response shapes.

## 2026-10-04 · Backend dependencies pinned; passlib dropped; AI_GATEWAY_STORE defaults to sql

**What:** `backend/requirements.txt` now pins the direct dependencies to the versions of the working venv (Python 3.13.6): fastapi 0.142.2, uvicorn[standard] 0.54.0, pydantic 2.13.5, pydantic-settings 2.15.0, sqlalchemy 2.1.3, psycopg2-binary 2.9.13, alembic 1.20.0, geoalchemy2 0.20.0, python-jose[cryptography] 3.5.0, bcrypt 5.0.0, python-multipart 0.0.32, redis 8.1.0, httpx 0.28.1, numpy 2.5.3, and the optional onnxruntime 1.30.0, Pillow 12.3.0, tokenizers 0.23.2. `bcrypt` is listed explicitly and `passlib` is removed (nothing imports it; `backend/core/security.py` uses bcrypt directly). `boto3` moved to `backend/requirements-s3.txt` (1.43.108, newest on PyPI; it is not in the venv, so that version was never run by the backend). `AI_GATEWAY_STORE` now defaults to `sql` (was `demo`); `demo` stays selectable, and the test run pins `demo` in the root `conftest.py`.

| Item | Design (section 27) | Pinned |
|---|---|---|
| FastAPI | 0.142.2 | 0.142.2 (matches) |
| SQLAlchemy | 2.0.54 | 2.1.3 |
| Alembic | 1.16.x | 1.20.0 |
| HTTP client (httpx) | current stable line | 0.28.1 |
| Async PostgreSQL driver | asyncpg | not used: psycopg2-binary 2.9.13 (sync) |
| Pydantic / Uvicorn | 2.x / current stable line | 2.13.5 / 0.54.0 (within the line) |
| Python | 3.14.x | 3.13.6 |

**Why:** Unpinned `>=` ranges let a fresh install resolve to different releases than the ones the tests ran on; the SQL-backed endpoints (`cases.py`, `main.py`, `ai_gateway/deps.py`) need the `sql` store, so the default must match what the API actually runs. This supersedes the "requirements are unpinned" note of the 2026-10-03 versions entry.
**Affects:** A `.env` that already sets `AI_GATEWAY_STORE=sql` is unchanged; anyone relying on the old implicit `demo` default must now set `AI_GATEWAY_STORE=demo`. Not verified on Python 3.14 or on SQLAlchemy 2.0.54 / Alembic 1.16.x.
