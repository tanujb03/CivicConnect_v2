# CivicConnect v2 backend

FastAPI modular monolith implementing design §51A. **Start with the "Backend" section of `docs/HANDOFF_LOCAL_SESSION.md`** (state, how to run, what is verified, what is missing) and `docs/BACKEND_AUDIT.md` (what was found).

```
api/v1/        thin routers (one file per area)        services/   domain logic; the only code that changes workflow state
models/        SQLAlchemy models (design §34)          schemas/    request / response models
core/          config, security, errors, pagination, idempotency, permissions
ai_gateway/    the only place routes meet ai.inference (demo store or SQL store)
events/        Redis Streams publisher + workers       storage.py  private object storage (local / S3)
scripts/       seed_demo, generate_openapi             tests/      SQLite unit tests + 3 PostgreSQL/PostGIS tests + a live-Redis test
```

Run: `.\scripts\dev\db_up.ps1` (PostGIS 18 + pgvector on port **5433**, Redis on 6379), then from the repository root `python -m alembic upgrade head`, `python -m backend.scripts.seed_demo`, `python -m uvicorn backend.main:app --reload`.
Health: `GET /api/v1/health/live` and `GET /api/v1/health/ready` (the health routes sit under the API prefix, not at `/health/...`); `ready` reports `database`, `storage` and `redis`.
Parallel sessions: `scripts\dev\new_worktree.ps1` gives each one its own worktree, database, Redis DB and port (`CLAUDE.md`, section 4).
