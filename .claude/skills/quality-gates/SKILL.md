---
name: quality-gates
description: The exact commands that must pass before every commit in the CivicConnect backend (pytest, ruff, alembic heads and check, Postgres/Redis tests) and how to report their counts. Use before each work-package commit and at the end of each wave.
effort: medium
---

# Quality gates (plan rule 9)

Run from the repo root in PowerShell with the shared venv (`& D:\Projects\CivicConnect_V2\.venv\Scripts\Activate.ps1`). Set `$env:TEMP='D:\ml-cache\tmp'; $env:TMP='D:\ml-cache\tmp'` first (C: is nearly full).

1. **Full suite:** `python -m pytest ai backend -q -rs`. State exact counts (`N passed, S skipped, F failed`) and list every skip reason. No new failures versus the previous recorded run.
2. **Lint the touched files only:** `python -m ruff check <files>` (root `ruff.toml`, line length 130). Do not add findings; older files may already have some.
3. **Migrations:** `python -m alembic heads` shows exactly one head. `python -m alembic check` shows "No new upgrade operations detected" (run it against PostgreSQL; the `vector` and `geography` columns are not comparable and warn).
4. **PostgreSQL and Redis tests (parent only; sub-agents never run these).** The dev containers are `civic-db` (host port 5433) and `civic-redis` (6379). Start them with `scripts\dev\db_up.ps1` if stopped. Use a throwaway test database with `postgis` and `vector`, never the dev database:
   - `$env:TEST_DATABASE_URL = '<postgresql+psycopg2 URL of a throwaway database, built from the lane or root .env pattern without printing it>'`
   - `$env:TEST_REDIS_URL = 'redis://localhost:6379/15'`
   - `python -m pytest backend/tests/test_postgres_integration.py backend/tests/test_postgres_vector_search.py backend/tests/test_events.py -q -rs`
   Drop the throwaway database and flush Redis DB 15 afterwards.
5. **OpenAPI:** if any route or schema changed, `python -m backend.scripts.generate_openapi`; a test fails when `backend/openapi.json` is stale.
6. **After a rebase:** repeat steps 1 and 3.

Reporting: give the commands and the exact counts; say plainly what failed, what was skipped and why, and what was not run. Never print secret values (names only; `python scripts/dev/env_names.py` shows names and set/empty).
