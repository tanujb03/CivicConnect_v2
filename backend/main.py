import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api.v1.router import api_router
from backend.core.config import DEV_SECRET, settings
from backend.core.exceptions import (
    CivicConnectException, civicconnect_exception_handler, http_exception_handler, unhandled_exception_handler, validation_exception_handler,
)
from backend.core.logging import setup_logging
from backend.core.rate_limit import rate_limit_dependency
from backend.core.telemetry import set_request_id, setup_telemetry, shutdown_telemetry, telemetry_kwargs

log = logging.getLogger("civicconnect.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup / shutdown lifecycle."""
    setup_logging()
    if settings.ENVIRONMENT.lower() == "prod" and settings.SECRET_KEY == DEV_SECRET:
        raise RuntimeError("SECRET_KEY must be set to a private random value when ENVIRONMENT=prod")
    setup_telemetry(app)                                 # WP8: nothing unless OTEL_ENABLED=true; raises a clear error if it is on and the packages are missing
    try:
        log.info("CivicConnect v2 API starting up...")
        if settings.AI_GATEWAY_STORE == "sql":
            from backend.ai_gateway import configure_gateway
            from backend.ai_gateway.sql import build_sql_gateway
            configure_gateway(build_sql_gateway())
            log.info("AI gateway reads cases from the database.")
        # Bootstrap Redis consumer groups (safe to call if Redis is offline)
        try:
            from backend.events import ensure_consumer_groups, start_background_workers
            ensure_consumer_groups()
            start_background_workers()
            log.info("Redis event system initialised.")
        except Exception as exc:
            log.warning("Event system startup skipped: %s", exc)
        yield
    finally:
        shutdown_telemetry()                             # flush spans (the workers are daemon threads), also when start-up fails
        log.info("CivicConnect v2 API shutting down.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    description="Backend API for CivicConnect v2 (design section 51A contract)",
    version="1.0.0",
    lifespan=lifespan,
    telemetry=telemetry_kwargs(),                           # WP8: FastAPI's native tracing, fully off unless OTEL_ENABLED=true
    dependencies=[Depends(rate_limit_dependency)],          # WP3: counts every request against its rule (off when RATE_LIMIT_ENABLED=false)
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_origins != ["*"],       # credentials are never combined with a wildcard origin
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Idempotent-Replayed", "Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Correlation id (§51A.1): echo the client's ``X-Request-ID`` (bounded) or mint one; hardening headers on every response."""
    request_id = request.headers.get("X-Request-ID", "")[:100] or str(uuid.uuid4())
    request.state.request_id = request_id
    set_request_id(request_id)                           # WP8: span attribute civic.request_id (no-op when telemetry is off)
    started = time.perf_counter()
    response = await call_next(request)
    if request.url.path.startswith(f"{settings.API_V1_STR}/") and not request.url.path.startswith(f"{settings.API_V1_STR}/health"):
        log.info("request %s %s -> %s in %d ms (request_id=%s)", request.method, request.url.path, response.status_code, (time.perf_counter() - started) * 1000, request_id)
    response.headers["X-Request-ID"] = request_id
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


app.add_exception_handler(CivicConnectException, civicconnect_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.PROJECT_NAME}", "docs": "/docs", "api": settings.API_V1_STR}
