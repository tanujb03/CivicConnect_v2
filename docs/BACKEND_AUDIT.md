# Backend audit (3 Oct 2026)

Scope: `backend/`, `alembic/` as received from Parth (commit `4f2e8c7`, "Backend addition - 4 phases with testing on mock data") against `docs/IMPLEMENTATION_PLAN_PARTH.md` (phases A–D, acceptance criteria for 2 Oct and 4 Oct) and the frozen design (§34 entities, §35 state machine, §41–§48, §51A contract).

## Verdict
Parth's commit is a **scaffold with mock responses, not a working backend**. The folder structure, router layout, error envelope, request-id middleware, Redis publisher (+ consumer-group bootstrap) and a good set of mock-based tests are real and were kept. Almost everything that touches data was a stub.

## What was there vs what the plan / contract needs (before this work)
| Area | State received | Evidence |
|---|---|---|
| DB models | 14 tables roughly named after §34, but with different columns (string ids like `CC-1A2B3C4D`, no `case_number`, `priority`, `ward_id`, `closed_at`, no `evidence.object_key/hash`, Geometry columns that only work on PostGIS) | `backend/models/*.py` |
| Migrations | **None.** `alembic/env.py` exists, `alembic/versions/` does not | `ls alembic` |
| Auth | Hard-coded `admin/admin` and `citizen/citizen` returning fixed ids; no register / refresh / `GET /auth/me`; `passlib` + `bcrypt 5` crashes on first hash; login takes OAuth2 form data, not the §51A.2 JSON `{identifier, password}` | `backend/api/v1/auth.py`, `security.py` |
| RBAC | JWT role check only; no object-level authorization (design §43); `GET /cases` and `/work-orders` needed no token | `cases.py` |
| Cases | `POST /cases` returned the literal `CC-MOCK-1`; list returned `[]`; get returned 404 always; no state machine (§35), no priority, no timeline, no verification logic, no PATCH, no contributors | `cases.py` |
| Evidence | multipart endpoint returned a fake URL; no `upload-init` / `complete` / signed URLs (§51A.6, §44) | `evidence.py` |
| Work orders | mock create; no start/complete; no case-scoped create (§51A.9) | `work_orders.py` |
| Map / analytics / incidents | empty FeatureCollections / zeros; paths differ from §51A (`/analytics/summary` vs `/analytics/overview`; no `/map/recurring-problems`, `/analytics/incidents`, `/incidents/{id}/cases`) | `map.py`, `analytics.py`, `incidents.py` |
| Sync | single-mutation endpoint that XADDs to Redis and says `queued`; §51A.16 requires a batch endpoint with per-mutation `APPLIED/ALREADY_APPLIED/REJECTED`, plus `GET /sync/changes` | `sync.py` |
| Idempotency | header accepted, never stored or enforced | all mutations |
| Pagination | `{items, next_cursor}` shape only; cursor never produced | |
| Health | `/health` only; §51A.17 `/health/live` and `/health/ready` missing | |
| Events (phase D) | publisher + groups real; workers only log | `events/` |
| AI hooks | good (Tanuj's gateway) but running on the synthetic demo city, not on DB cases | `ai_gateway/` |
| Infra | no `infra/`, no Dockerfile / compose | plan §4 |
| Hygiene | `__pycache__/*.pyc` committed; CORS `*` with credentials | repo |
| Tests | 64 mock-only tests that assert the mock behaviour (e.g. "list cases without auth returns data") | `test_phase_c/d.py` |

Plan acceptance criteria for "2 Oct night": boots (yes), migrations run (**no**), DB schema exists (**no**), auth works for demo roles (mock only), core case CRUD (**mock**), evidence upload-init flow (**no**), OpenAPI generated (yes, stale), basic API tests (mock), health (partial). For "4 Oct": nothing beyond the AI hooks.

## What this branch changes
See the "Backend" section of `docs/HANDOFF_LOCAL_SESSION.md` for the current state, endpoint list and how to run it. The detailed per-endpoint status table is at the end of that section and is verified by tests (`backend/tests/test_api_*.py`, `test_contract_51a.py`, and the PostgreSQL/PostGIS integration test).

## Honest limits that remain (also listed in the handoff)
Rate limiting / abuse controls, OTP login, web push, malware scanning of uploads, OpenTelemetry tracing, pgvector search and a real object store were not exercised against live services from the cloud session; each is flagged where it applies.
