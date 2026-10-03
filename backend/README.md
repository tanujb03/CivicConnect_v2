# CivicConnect v2 backend

FastAPI modular monolith implementing design §51A. **Start with the "Backend" section of `docs/HANDOFF_LOCAL_SESSION.md`** (state, how to run, what is verified, what is missing) and `docs/BACKEND_AUDIT.md` (what was found).

```
api/v1/        thin routers (one file per area)        services/   domain logic; the only code that changes workflow state
models/        SQLAlchemy models (design §34)          schemas/    request / response models
core/          config, security, errors, pagination, idempotency, permissions
ai_gateway/    the only place routes meet ai.inference (demo store or SQL store)
events/        Redis Streams publisher + workers       storage.py  private object storage (local / S3)
scripts/       seed_demo, generate_openapi             tests/      113 tests (SQLite) + 3 PostgreSQL/PostGIS tests
```
