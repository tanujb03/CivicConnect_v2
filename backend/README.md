# CivicConnect v2 backend

FastAPI modular monolith implementing design §51A. **Start with the "Backend" section of `docs/HANDOFF_LOCAL_SESSION.md`** (state, how to run, what is verified, what is missing) and `docs/BACKEND_AUDIT.md` (what was found).

```
api/v1/        thin routers (one file per area)        services/   domain logic; the only code that changes workflow state
models/        SQLAlchemy models (design §34)          schemas/    request / response models
core/          config, security, errors, pagination, idempotency, permissions
ai_gateway/    the only place routes meet ai.inference (demo store or SQL store)
events/        Redis Streams publisher + workers       storage.py  private object storage (local / S3)
scripts/       seed_demo, demo_reset, backfill_embeddings,  tests/      SQLite unit tests + PostgreSQL/PostGIS and live-Redis tests
               calibrate_duplicates, generate_openapi,                   (they skip when TEST_DATABASE_URL / TEST_REDIS_URL are not set)
               rescan_evidence
```

Run: `.\scripts\dev\db_up.ps1` (PostGIS 18 + pgvector on port **5433**, Redis on 6379), then from the repository root `python -m alembic upgrade head`, `python -m backend.scripts.seed_demo`, `python -m uvicorn backend.main:app --reload`.
Health: `GET /api/v1/health/live` and `GET /api/v1/health/ready` (the health routes sit under the API prefix, not at `/health/...`); `ready` reports `database`, `storage` and `redis`.
Parallel sessions: `scripts\dev\new_worktree.ps1` gives each one its own worktree, database, Redis DB and port (`CLAUDE.md`, section 4).

Tools (all from the repository root; `python -m ...` so the lane's own code wins on `sys.path`):

| Need | Command |
|---|---|
| Full suite | `python -m pytest ai backend -q` (set `TEST_DATABASE_URL` / `TEST_REDIS_URL` for the PostgreSQL and Redis tests: 1621 passed, 5 skipped on 2026-10-09) |
| Demo reset (city + one scripted case per lifecycle stage, **keeps stored embeddings**, no provider call) | `python -m backend.scripts.demo_reset` |
| Demo snapshot / restore (embeddings included, about 3 s) | `.\scripts\dev\snapshot_demo_db.ps1`, `.\scripts\dev\restore_demo_db.ps1 -Yes` |
| End-to-end HTTP smoke against a running API | `python scripts/dev/smoke.py --no-ai [--scan] [--forwarded-for]` |
| Embeddings for cases that lack one (quota-paced, dry-run first; asks for the owner's go) | `python -m backend.scripts.backfill_embeddings --dry-run`, see `docs/AI_LIVE_CHECK.md` |
| Duplicate thresholds from stored embeddings (no provider call) | `python -m backend.scripts.calibrate_duplicates` |
| OpenAPI file + typed TypeScript client | `.\scripts\dev\gen_api_client.ps1` (`packages/api-client`) |
| Tracing (off by default) | `OTEL_ENABLED=true`, Jaeger via the compose `obs` profile (`docs/infra/COMPOSE.md`) |

Compose stack from empty volumes (db, redis, backend, optional `scan`, `s3`, `obs`): `docs/infra/COMPOSE.md`. Phone access: `docs/infra/TUNNEL.md`. Frontend contract: `docs/FRONTEND_API_NEEDS.md`.
