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

## 2026-10-04 · A12 roles: the design's SUPER_ADMIN is the code's SYSTEM_ADMIN; elevated roles are SYSTEM_ADMIN-only

**What:** Design A12 lists the roles CITIZEN, FIELD_WORKER, DEPARTMENT_OPERATOR, DEPARTMENT_MANAGER, WARD_OFFICER, CITY_ADMIN and SUPER_ADMIN. The implemented role set (design §51A.2, `backend/models/user.py`) has SYSTEM_ADMIN where the design says SUPER_ADMIN and also an OVERLOOKER, and no `SUPER_ADMIN` value exists or was added. User management (`/admin/users`) treats **CITY_ADMIN and SYSTEM_ADMIN as the elevated roles**: both may manage users (capability `manage_users`), but only a SYSTEM_ADMIN may grant an elevated role or change, deactivate or reactivate a user who holds one. Nobody can change their own role or deactivate themselves. Staff accounts are created with a generated one-time password that is returned once; there is no password change or reset endpoint yet (OTP login is deferred, see above), so that password stays valid until one exists.
**Why:** Adding a role value would have needed a data and contract change for no functional gain; the rule "only the top role grants elevated roles" is what the A12 sentence asks for. Self-protection avoids locking the last administrator out.
**Affects:** `GET/POST /admin/users`, `PATCH /admin/users/{id}`; the new capability `manage_settings` (CITY_ADMIN, SYSTEM_ADMIN) appears in `access_scope.capabilities` of `/me`. A city admin cannot edit another city admin or a system admin.

## 2026-10-04 · A13 system settings: six typed keys; two are applied, four stored

**What:** `GET/PUT /admin/settings` over `system_settings` with the keys `ai_confidence_threshold`, `duplicate_threshold`, `sla_hours_by_priority`, `supported_languages`, `notification_policy`, `flag_review_threshold` (validated, audited per changed key). Design A13 also lists categories, subcategories, departments, ward boundaries, escalation rules and moderation rules as configurable: those are **not** settings keys in V1 (the taxonomy is read-only through `/reference/taxonomy`). `ai_confidence_threshold` now overrides `ai_policy.v1.json` `intake.low_confidence_threshold` and `duplicate_threshold` overrides `fusion_policy.v1.json` `thresholds.possible_duplicate` (`related` stays 0.5, capped by the duplicate threshold) in the AI gateway; the other four keys are stored and returned only (case SLA is still computed from the taxonomy, the notification channels and the flag review are not wired to them yet). `ai/inference/**` was not edited: the gateway writes the values into the policy dicts of its own AIService and its own deep copy of the cached fusion policy.
**Why:** The policy files say their thresholds are "admin-adjustable per A13"; a copy per gateway keeps the cached file contents unchanged for everything else. Defaults of the two applied keys are read from those files, so an unset key behaves exactly as before. `notification_policy` defaults to push only because no free email or SMS provider is wired.
**Affects:** Only the SQL-backed gateway (`AI_GATEWAY_STORE=sql`) reads settings; the in-memory demo gateway keeps the file values. A change reaches other processes within 5 seconds (immediately in the process that handled the PUT).

## 2026-10-04 · Analytics for the admin and overlooker apps (additive, one meaning change)

**What:** New `GET /analytics/trends` (daily or weekly counts by category and status, SQL group-by, role-scoped) and `GET /reference/{taxonomy,departments,wards}` (ETag + Cache-Control). Extended, additive: department analytics gained `name`, `days`, `by_severity`, `recurring_cases`; ward analytics gained `name`, `critical`, `backlog`, `median_resolution_days`, `recurrence`, `by_category`; overview gained `priority_distribution` and `severity_distribution`. **Meaning change:** on `/analytics/departments` and `/analytics/departments/{id}` the fields `resolved`, `median_resolution_hours` and `sla_compliance_pct` now cover cases closed in the last `days` days (default 30, parameter `days`); they used to cover every case ever resolved.
**Why:** The A07 page labels these numbers "Resolved (30d)" and shows incoming (30d); an all-time resolved count next to a 30-day incoming count is not comparable. Everything else only adds fields.
**Affects:** Any client of the department endpoints that relied on the all-time numbers (none in the repo). Shapes and the list of data the apps want but the backend cannot provide: `docs/FRONTEND_API_NEEDS.md`.

## 2026-10-04 · Gold-set provenance: gold rows are no longer assumed to be team-written

**What:** `text_corpus.build` used to write every gold row as `label_origin=team_authored`, `synthetic=False`. Each row now carries a `provenance` (`human` only when explicitly marked, `llm_authored_<model>`, else `unspecified`), read from a new `provenance` CSV column or an `llm_authored_*` marker in `notes` (`ai/evaluation/gold.py`). `label_origin` / `synthetic` follow it (`team_authored` / False only for `human`; everything else True). The corpus manifest gains `gold.by_provenance`. The M6 evaluation (`text_model/train.py`) reports gold as one block per provenance, `gold[<provenance>, n=<rows>]`, never pooled, instead of one block named `gold`; notebook 07 checks for those blocks. The gold CSV template has a fifth `provenance` column.
**Why:** The 336-line cross-family set `ai/training/gold/gold_llm_authored_claude_v1.csv` is LLM-written; the old defaults would have labelled it, and any report using it, as human gold. Unknown provenance must never read as human.
**Affects:** Only `ai/training` and `ai/evaluation` (no `ai/inference` change, no API change). A `gold.jsonl` built before this change has no provenance and is reported as `unspecified`: rebuild the corpus. The team's own gold CSV must put `human` in the `provenance` column to count as human gold. `info["results"]["gold"]` no longer exists; use the `gold[...]` keys.

## 2026-10-08 · Backend build plan: one session, no lanes; hooks and sub-agents

**What:** `docs/BACKEND_BUILD_PLAN.md` orders the remaining backend work. For this work it replaces the lane structure of `CLAUDE.md` sections 4 and 6: one session in the main checkout on `tanuj`, sub-agents (`backend-implementer`, `backend-reviewer`) for work packages, no `new_worktree.ps1`. `CLAUDE.md` now says so at the top. Safety hooks (`.claude/hooks/guard.py`, wired in the gitignored `.claude/settings.local.json`) block force-push, push to `main`, `reset --hard`, `clean -f`, volume deletion, trailer text in commit messages, printing the env file, and cross-role edits (`CC_ROLE`).
**Why:** The lanes were built for four parallel sessions; the build is now one backend session plus a frontend session, and the plan makes the shared-file and Alembic ownership rules explicit.
**Affects:** Process only. The old lanes under `D:\cc` still exist and hold no unpushed work (census 2026-10-08).

## 2026-10-08 · Honesty sweep: no model is trained; `packages/api-client` does not exist yet; the containers are not always running

**What:** `CLAUDE.md`, `docs/HANDOFF_LOCAL_SESSION.md` (section 4) and `docs/RUNBOOK_ML.md` no longer say M3/M4 "are trained". Truth: the AI layer uses pretrained hosted models through `AIProvider`; the B0 classifier and the fusion calibrator are small baselines once fitted on synthetic data, their weights are not on the laptop, and nothing loads them unless `AI_LOCAL_CLASSIFIER_PATH` / `AI_FUSION_WEIGHTS_PATH` is set. The plan trains nothing. `CLAUDE.md` also records that `packages/api-client` is created in WP9 (it was listed as existing) and that the Docker containers must be started (they had been stopped for days).
**Why:** The 2026-10-08 census found no trained weights on disk and no `packages/api-client`; repeating the old statements would mislead the team and any report built from them.
**Affects:** Documentation only. No code or API change.

## 2026-10-08 · Migration 0004: forced password change columns and worker indexes

**What:** Revision `0004` (the only new revision of the build plan): `users.must_change_password BOOLEAN NOT NULL DEFAULT false`, `users.password_changed_at TIMESTAMPTZ NULL`; indexes `ix_device_tokens_user_active (user_id, revoked_at)`, `ix_notif_push_status (push_status, created_at)`, `ix_evidence_scan_status (scan_status)`, `ix_case_flags_case_status (case_id, status)`. The unique `(case_id, user_id, kind)` on `case_flags` already existed (`uq_case_flag`, 0003). Models updated to match; reversible; verified on SQLite and PostgreSQL (upgrade, `downgrade -1`, upgrade, `alembic check`).
**Why:** WP2 (change/reset password with forced change), WP4 (open-flag counts), WP5 (push worker), WP6 (scan worker and quarantine gate) need these and no other schema change.
**Affects:** Existing rows get `must_change_password = false`, so nobody is locked out by the upgrade. No API change yet (WP2 exposes the flag). `test_migration_0003.py` now downgrades to `0002` instead of `-1`, and `test_postgres_integration.py` expects head `0004`.

## 2026-10-08 · Tests: optional packages skip instead of failing; the I18N review doc has repo-relative paths

**What:** Test modules that need `nbformat`, `scikit-learn` or `scipy` skip with a reason when the package is missing or unusable (an OS Application Control policy can block scikit-learn's compiled `_libsvm`); helper `ai/training/tests/optional_deps.py`. `ai.training.src.text_corpus.review_sample` writes the gold-set path relative to the repository root, and `docs/I18N_REVIEW.md` was regenerated (it contained `D:/cc/b/...`). No test assertion was changed; one regression test was added.
**Why:** In a clean venv with only `backend/requirements.txt` plus pytest, `pytest ai backend -q` must give 0 failures (it had collection errors and 10 failures from missing optional packages); the review doc test failed on every checkout except one old lane.
**Affects:** Test code and the doc generator only.

## 2026-10-08 · WP2 auth hardening: change and reset password, forced change (additive)

**What:** New `POST /auth/change-password` (policy: at least 10 characters, not the current password, not a deny-listed or demo password; revokes every refresh token; returns a fresh session; audit `user.password_changed`) and `POST /admin/users/{id}/reset-password` (CITY_ADMIN, SYSTEM_ADMIN; one-time password returned once; audit `user.password_reset`). `POST /admin/users` creates staff with `must_change_password = true`. New field `must_change_password` on the user object of every session response, on the profile (`/auth/me`, `/me`) and on the admin user objects. While it is true every endpoint except change-password, logout, refresh and `/auth/me` answers `403 PASSWORD_CHANGE_REQUIRED` (also the AI gateway routes, which authenticate separately). New codes: `CURRENT_PASSWORD_INCORRECT` (400), `WEAK_PASSWORD` (422), `PASSWORD_CHANGE_REQUIRED` (403). Shapes: `docs/FRONTEND_API_NEEDS.md` section 6.
**Why:** Admin-created accounts used a one-time password with no way to replace it, and there was no password change at all.
**Affects:** Additive. A client that ignores the new field keeps working until it meets a staff account created or reset after this change (it then gets `PASSWORD_CHANGE_REQUIRED` on every call, so the staff apps need the change-password screen). Known limit: access tokens carry no `iat`, so an old access token stays valid until it expires (30 min) after a change or reset; only refresh tokens are revoked.

## 2026-10-08 · WP3 rate limiting (additive)

**What:** One global dependency counts every request under `/api/v1` (health probes excepted) in Redis fixed windows with an in-process fallback (warning at most once a minute) and answers `429 RATE_LIMITED` with `Retry-After` and `X-RateLimit-Limit/Remaining/Reset`; `details` carry `retry_after_seconds`, `limit`, `window_seconds`, `rule`. `CivicConnectException` gained an optional `headers` argument; CORS exposes the four headers. The sign-in lockout (5 failures per identifier per minute) now uses the shared sliding-window `FailureCounter` (Redis, in-process fallback) instead of a per-process dict. Settings `RATE_LIMIT_*` (defaults in `backend/core/config.py`); off when `RATE_LIMIT_ENABLED=false` or `ENVIRONMENT=test`. The signed-media routes are counted like any other (by IP); only `/health*` is exempt (design decision of this review: the anonymous PUT must not be unthrottled).
**Why:** The AI endpoints spend free-tier provider quota, and sign-in and registration were unprotected across workers.
**Affects:** Additive for clients that handle 429. Deployment note: behind a proxy or tunnel set `RATE_LIMIT_TRUST_FORWARDED_FOR=true` (rightmost `X-Forwarded-For` entry), otherwise all clients share one per-IP bucket (10 sign-ins per minute for everybody). Not run against a real Redis yet (fake Redis in the unit tests; the Redis-backed run is part of the wave-end checks).

## 2026-10-08 · AI gateway: per-model budgets, quota-aware cooldown, Groq text fallback, optional cache, language hint, voice note without transcript

**What:** (1) Per-model request budgets (requests per minute and per day, tokens per minute) from `backend/ai_gateway/providers/model_limits.json` (quota numbers of 2026-10-08, not model choices), overridable with `AI_MODEL_LIMITS`: a full minute budget waits at most `AI_BUDGET_MAX_WAIT_S`, a spent daily budget sends nothing and the call degrades; the daily counter is in Redis with an in-process fallback; the single per-provider Gemini limit is gone. (2) After HTTP 429 a model is not called again for a while: until the Pacific-midnight reset for a per-day quota, otherwise the provider's retry delay (60 s default); the error now carries Google's `QuotaFailure`/`RetryInfo` fields. (3) `AI_FALLBACK_TEXT_MODEL`: a Groq text model used once when the Gemini call cannot be served; never for images; no default model is ever chosen by code. (4) `AI_CACHE_ENABLED` (default off): Redis cache of successful primary-model answers; it stores citizen text/image/audio answers for `AI_CACHE_TTL_S`, so it stays off for real data. (5) `AI_EMBEDDING_DIM` (768): requested from the provider, length checked, vector L2-normalised. (6) `POST /cases/intake/analyze`: `language_hint` (else the profile's `preferred_language` when it is `hi` or `mr`, never `en`) goes to speech-to-text; **a report that is only voice notes with no usable transcript now answers 200 with an empty draft and warning `TRANSCRIPTION_UNAVAILABLE` instead of 422** (a contract change for the citizen app: `docs/FRONTEND_REQUESTS.md`).
**Why:** The 2026-10-08 live check showed the flash model's free daily cap is 20 requests and that every blocked call cost 12 to 15 s before degrading; a voice-note-only report is the normal case for a citizen who cannot type.
**Affects:** Additive except (6): the status code of that one situation changes from 422 to 200. Quota numbers change over time: edit the JSON or set `AI_MODEL_LIMITS`.

## 2026-10-08 · WP4 community flags (additive)

**What:** `POST /cases/{id}/flags`, `GET /cases/{id}/flags` (staff), `POST /flags/{id}/resolve` (staff); codes `FLAG_ALREADY_EXISTS` (409), `FLAG_NOT_ALLOWED` (403), `FLAG_NOT_FOUND` (404), `FLAG_ALREADY_RESOLVED` (409). New staff-only fields on case objects: `open_flag_count`, `needs_flag_review`, `map_hidden`. Notification type `CASE_FLAG_REVIEW`; internal timeline events `FLAG_REVIEW_REQUESTED`, `FLAG_RESOLVED`. **Clarification of the plan's "until resolved":** a case with open `INAPPROPRIATE` flags at or above `flag_review_threshold` is hidden from the NON-staff map, and it stays hidden while any `INAPPROPRIATE` flag is UPHELD (staff agreed it is inappropriate); resolving everything DISMISSED lifts it. Staff keep their operational view of the map. The notification text is English only (no new hi/mr template needing native review).
**Why:** Citizens needed a way to report stale or inappropriate cases; the review found that letting an UPHELD flag un-hide the case would defeat the point.
**Affects:** Additive. Known limits: the review notification can race on PostgreSQL (the derived `needs_flag_review` is still correct); coordinated accounts could hide a case from the public map until staff act (staff are alerted at the threshold and can lift it).

## 2026-10-08 · WP5 Expo push (additive)

**What:** `POST/GET /me/devices`, `DELETE /me/devices/{id}` (Expo tokens, at most `PUSH_MAX_DEVICES_PER_USER` active per user). `notify()` marks new notifications `PENDING` for users with an active token while `notification_policy.push` is on; a worker thread (`backend/events/push_worker.py`) sends them to Expo in batches of at most 100 and polls receipts; transient failures (429, 5xx, timeouts) and config errors (401/403) never consume an attempt, a 400 is bisected to the bad message, `DeviceNotRegistered` revokes the token. Delivery is at-least-once. Nothing is sent in tests. Not implemented: `device_id` on logout (it needs a `RefreshIn` schema change and `/auth/logout` has no authenticated user); apps call `DELETE /me/devices/{id}` before signing out.
**Why:** The citizen and field-worker apps are Expo apps and need push for status changes and work orders.
**Affects:** Additive. A token that belonged to another account is moved to the caller (audited as `device.rebound`); on a shared phone the previous user keeps receiving pushes until the next user registers or the app revokes the device. Remote push needs a development build, not Expo Go.

## 2026-10-08 · WP6 upload malware scan (additive)

**What:** `SCAN_ENABLED` (default false), `CLAMD_HOST/PORT`: a worker (`backend/events/scan_worker.py`) streams READY evidence to clamd (INSTREAM) and records `CLEAN`/`INFECTED`/`ERROR`; with scanning off new rows are `UNSCANNED`. `EvidenceOut.scan_status`. Gate: `INFECTED` is never downloadable (403 `EVIDENCE_QUARANTINED`), invisible to non-staff, skipped by the AI evidence resolver; `PENDING` (403 `EVIDENCE_SCAN_PENDING`) and `ERROR` (403 `EVIDENCE_SCAN_FAILED`) are refused while scanning is on. The signed upload link is closed once `complete` runs (409 `EVIDENCE_LOCKED`) and the verdict is bound to the stored sha256 (a changed file becomes `ERROR`). `python -m backend.scripts.rescan_evidence` re-queues `ERROR` or `UNSCANNED` rows. Not built: a clamd health check in `/health/ready`.
**Why:** Design §44; uploaded files are served to staff and other users.
**Affects:** Additive; two new 403 codes and one 409 code. Known limits: with S3 the presigned PUT window (at most `SIGNED_URL_TTL_SECONDS`) and presigned GET links issued before a verdict cannot be revoked; attempt counters are per process; the real-clamd EICAR test was not run (clamd is not started on this machine).

## 2026-10-08 · WP7 embedding backfill and duplicate-threshold calibration (additive, no schema or API change)

**What:** `AIGateway.embed_cases` (one embedder call per batch) and `SqlCaseRepository.save_embedding(if_missing=)` / `embedded_ids` for the quota-paced `python -m backend.scripts.backfill_embeddings` (`--dry-run`, `--limit`, `--batch-size`, `--max-requests`): it embeds only cases that have NO embedding row, never re-embeds one, stays under 80 requests and 25,000 estimated tokens per minute, is resumable, stops with exit code 2 on a 429, a spent daily budget or `--max-requests`, and prints the requests it used and the daily-counter delta. Each batch is one attempt (`AI_MAX_RETRIES=0`), rejected rows are bisected and skipped, and a run of more than 100 inputs needs `--counting per-batch|per-input` (the owner states what AI Studio's usage page showed for the 10-input probe) and a daily limit. `python -m backend.scripts.seed_demo --with-embeddings` (default off) only prints the dry-run plan and the commands to run. The embedder is gemini-embedding-001 through the provider at 768 dimensions (AI_EMBEDDING_DIM); nothing is trained; a local multilingual-e5-small ONNX embedder is NOT built (owner decision pending). `python -m backend.scripts.calibrate_duplicates` derives the duplicate and related thresholds from the planted pairs of the demo city; the deterministic gate (category, radius, time window) stays primary and embeddings only rank candidates inside it. It refuses below 90% embedding coverage and states that 27 positives are too few for any real-world claim.
**Why:** The 560 demo cases have no embeddings and the embedding model allows 1000 requests per day and 30K tokens per minute; observed cosines (0.69 for unrelated text, 0.91 for a true Hindi/English match) show a bare cutoff is not enough.
**Affects:** Nothing at runtime. Dry-run on the dev database (nothing sent): 560 cases to embed, 12 batches of 50, about 14.8K estimated tokens, at least 0.6 minutes; 12 requests if a batch counts as one request, 560 if every input counts. Which one is true is unknown until a small real run is compared with AI Studio's usage page. The policy file `fusion_policy.v1.json` is not edited by the script.
**Update (same day, measured):** the 10-input probe moved AI Studio's requests-per-day for the embedding model by **10**: every input of a batch counts as one request. `model_limits.json` now marks `gemini-embedding-001` `count: per_input` (also `AI_MODEL_LIMITS=model=rpm/rpd/tpm/input`): the minute window and the daily counter count inputs (`ModelBudgets.acquire(..., units=)`), and a batch that would pass the daily limit is refused before it is sent. The backfill gained `--daily-ceiling N` (hard stop) and `--assume-used-today M` (what AI Studio showed before the run).

## 2026-10-08 · AI gateway: request deadline, provider timing, 429 cooldown by quota id

**What:** `AI_PROVIDER_TIMEOUT_S` (default 20) bounds ONE provider call including retries, throttle and budget waits; `AI_REQUEST_DEADLINE_S` (default 30) bounds all provider calls of one API request (primary, Groq fallback, localization): a call that cannot finish inside what is left is not started and the gateway degrades with the usual warnings. A timeout never starts the 429 cooldown. Each provider call logs one INFO line (`provider_ms` separately from `waited_ms`), and intake, triage, copilot and analytics-explain add `ai_metadata.timing {provider_ms, waited_ms, total_ms, provider_calls, request_deadline_s}`; the API logs `request METHOD path -> status in N ms`.
**Why:** One Hindi intake took 29 s in the live pass (cause unknown); with retries and the free-tier spacing the worst case was far above any acceptable request time.
**Affects:** Additive (`ai_metadata.timing` is a new optional key). A slow provider now degrades after about 20 s instead of up to a minute or more.

## 2026-10-08 · WP8 OpenTelemetry (additive, off by default)

**What:** `OTEL_ENABLED=true` turns on tracing: FastAPI's native server spans (FastAPI 0.142 has native OpenTelemetry), SQLAlchemy, Redis and httpx client spans, trace context in the Redis stream envelope (`traceparent`/`tracestate`) so API, worker and the AI call are one trace, `service.name=civicconnect-backend`, request id as `civic.request_id`, OTLP/HTTP export to `OTEL_EXPORTER_OTLP_ENDPOINT` (default `http://localhost:4318`, `http://jaeger:4318` in compose). Pins: opentelemetry-api, -sdk and the OTLP/HTTP exporter 1.45.1; the SQLAlchemy, Redis and httpx instrumentations 0.66b1; greenlet 3.5.6 (needed by the SQLAlchemy instrumentation with SQLAlchemy 2.1). The SQLAlchemy instrumentation declares `sqlalchemy<2.1`; it is used with `skip_dep_check=True` (upstream issue python-contrib#5118). Query strings are redacted before export; a telemetry fault can never lose an event or skip a handler.
**Why:** Design §47; one trace from the request to the worker and the AI call.
**Affects:** **OpenTelemetry is only activated when `OTEL_ENABLED=true`. There is no guarantee that no `opentelemetry` module is imported while it is off** (FastAPI and redis-py import parts of it themselves); while off no tracer provider, exporter or instrumentation is installed. **Parentless background HTTP spans (for example the Expo push sends, scan-worker calls, stream polls) are not traced** by design. Exception messages recorded on spans are not redacted. The Jaeger acceptance (one trace for a created case) is verified separately (see the status table).

## 2026-10-08 · Access tokens carry `iat`; logout revokes a push device

**What:** Access tokens carry an integer `iat` and are refused with `401 AUTH_INVALID_TOKEN` when issued before the user's last password change (`password_changed_at`, also set by an admin reset), or when they have no `iat` and a change happened; the user row is already loaded, so there is no extra query; the AI gateway routes use the same check. `POST /auth/logout` accepts an optional `expo_push_token` and revokes that device of the refresh token's owner (only when the refresh token was live); `DELETE /me/devices/{id}` stays.
**Why:** Closes the documented 30-minute window after a password change and the shared-phone push leak.
**Affects:** The documented limit is removed from `docs/FRONTEND_API_NEEDS.md`. A token issued in the same second before a change may survive that second. After an admin reset an old token now gets 401 (it used to get 403 `PASSWORD_CHANGE_REQUIRED`).

## 2026-10-09 · WP9 typed API client; logout push token is lenient
**What:** New `packages/api-client` (`@civicconnect/api-client`): types generated from `backend/openapi.json` with openapi-typescript 7.13.0 plus a thin `openapi-fetch` 0.17.0 wrapper (bearer token, single-flight 401 refresh with one retry on the same `Idempotency-Key`, `Idempotency-Key` on mutations, `ApiError`, cursor pagination). `scripts/dev/gen_api_client.ps1` regenerates it; `backend/tests/test_api_client_generated.py` fails when `openapi.json` and the recorded SHA-256 in `packages/api-client/src/schema.sha256` disagree. `LogoutIn.expo_push_token` is now only length-limited (2000), no longer pattern-checked (`openapi.json` regenerated).
**Why:** WP9 of the build plan; and a stale or odd push token must never stop a user from signing out (it used to be a `422`, which left the refresh token live).
**Affects:** Additive for the apps. The one behaviour change is that a malformed `expo_push_token` on logout is now a `200` that revokes no device (`docs/FRONTEND_API_NEEDS.md` and `docs/FRONTEND_REQUESTS.md` say so).

## 2026-10-09 · WP11: smoke test, demo reset, snapshots, CORS defaults, compose scan wiring
**What:** `scripts/dev/smoke.py` (the full HTTP loop plus negative checks; `--scan`, `--forwarded-for`, `--no-ai`), `python -m backend.scripts.demo_reset` (reseeds the city, **keeps the stored embeddings** and adds six scripted cases through the API, one per stage, no provider call; `--allow-reembed` is the only way to drop vectors), `scripts/dev/snapshot_demo_db.ps1` / `restore_demo_db.ps1` (pg_dump / pg_restore, embeddings included). `seed.reset_all` uses `TRUNCATE ... CASCADE` on PostgreSQL (the work_orders / evidence_items cycle made the table-by-table DELETE fail on any database that held evidence). The default `CORS_ORIGINS` now also lists `http://localhost:8080`, `8081`, `8082` and `19006` (admin and overlooker Vite, Expo web); the compose backend passes `SCAN_ENABLED` and `CLAMD_HOST`.
**Why:** WP11 of the build plan; the admin and overlooker dev servers (port 8080) were blocked by CORS with the old defaults; the compose `scan` profile could not be used because the backend never received the scan settings.
**Affects:** Additive. Local-origin CORS entries only (never `*`, credentials stay on). `docs/infra/COMPOSE.md` and `docs/infra/TUNNEL.md` record what was and was not verified.
**Review (backend-reviewer, 2026-10-09):** no blocker; the 4 majors were fixed (demo_reset / `seed_demo --reset` refuse a non-local database host without `--allow-remote` and print the target; the embeddings spill file is owner-only, randomly named, kept with a printed `--restore-spill` command when the run fails after the wipe, removed otherwise; the smoke `--scan` EICAR check is labelled as the type check it is, clamd detection itself is `test_eicar_against_a_real_clamd`; smoke refuses a non-private `--base-url` without `--allow-remote` and also tries a wrong-key JWT and an `alg=none` JWT). PowerShell scripts validate database / snapshot / container names. Left as documented limits: the default localhost CORS origins also apply when `ENVIRONMENT=prod` and `CORS_ORIGINS` is unset (set it); a restore of saved vectors is keyed by case id only (the demo dataset ids are fixed, so a changed dataset text would keep an old vector: use `--allow-reembed` then); the pgvector text round trip of `demo_reset` is verified by an md5 over the 560 real vectors, not by a unit test (the unit tests run on SQLite); provider isolation in `demo_reset` is by removing keys and stubbing the loaders, proven by unchanged quota counters, not by a test; the snapshot dump contains password hashes of demo users.

## 2026-10-09 · README Roadmap brought in line with what is built
**What:** The Roadmap list in `README.md` no longer lists Expo push, malware scanning, tracing and the typed API client as future work; it says they are built (with their unverified edges) and keeps Tamil / further languages, metrics dashboards and the Hindi / Marathi wording review as open.
**Why:** The list contradicted the code (found in WP12); the owner asked for the remaining roadmap to be worked through.
**Affects:** Documentation only.
