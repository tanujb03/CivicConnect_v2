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
