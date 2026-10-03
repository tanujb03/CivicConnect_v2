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


@router.get("/health/ready")
def ready(response: Response):
    """§51A.17 readiness: required dependencies (database, object storage) must work; Redis is optional infrastructure and is reported as ``degraded`` when absent.
    The body contains no citizen data."""
    from backend.db import session as db_session
    checks: dict[str, str] = {}
    try:
        with db_session.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
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
    return {"status": "ready" if required_ok else "not_ready", "checks": checks, "environment": settings.ENVIRONMENT}
