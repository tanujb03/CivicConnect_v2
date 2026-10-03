import logging

from fastapi import APIRouter, Response
from sqlalchemy import text

from backend.core.config import settings

router = APIRouter()
log = logging.getLogger("civicconnect.health")


@router.get("/health")
async def health_check():
    """Legacy alias of ``/health/live``."""
    return {"status": "ok", "message": "CivicConnect v2 Backend is healthy"}


@router.get("/health/live")
def live():
    """§51A.17 process liveness only; touches nothing."""
    return {"status": "ok"}


def _vector_search_enabled(conn) -> bool:
    """True when pgvector is installed AND migration 0003 created ``case_embeddings.embedding_vec`` (PostgreSQL only; SQLite and a server without the extension: False)."""
    if conn.dialect.name != "postgresql":
        return False
    return bool(conn.execute(text(
        "SELECT 1 FROM pg_extension e, information_schema.columns c WHERE e.extname = 'vector' AND c.table_schema = current_schema() "
        "AND c.table_name = 'case_embeddings' AND c.column_name = 'embedding_vec'")).scalar())


@router.get("/health/ready")
def ready(response: Response):
    """§51A.17 readiness: required dependencies (database, object storage) must work; Redis is optional infrastructure and is reported as ``degraded`` when absent.
    ``vector_search`` says whether pgvector similarity search is available (optional, never affects readiness). The body contains no citizen data."""
    from backend.db import session as db_session
    checks: dict[str, str] = {}
    vector_search = False
    try:
        with db_session.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            try:
                vector_search = _vector_search_enabled(conn)
            except Exception as e:
                conn.rollback()
                log.warning("readiness: vector_search probe failed: %s", type(e).__name__)
        checks["database"] = "ok"
    except Exception as e:
        log.error("readiness: database check failed: %s", type(e).__name__)
        checks["database"] = "unavailable"
    try:
        from backend.storage import get_storage
        store = get_storage()
        store.size("healthcheck/none")                     # a metadata call, no write
        checks["storage"] = "ok"
    except Exception as e:
        log.error("readiness: storage check failed: %s", type(e).__name__)
        checks["storage"] = "unavailable"
    try:
        from backend.events import get_redis
        checks["redis"] = "ok" if get_redis() is not None else "degraded"
    except Exception:
        checks["redis"] = "degraded"
    required_ok = checks["database"] == "ok" and checks["storage"] == "ok"
    if not required_ok:
        response.status_code = 503
    return {"status": "ready" if required_ok else "not_ready", "checks": checks, "vector_search": vector_search, "environment": settings.ENVIRONMENT}
