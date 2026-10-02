import uuid
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from backend.core.config import settings
from backend.api.v1.router import api_router
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from backend.core.exceptions import (
    CivicConnectException, civicconnect_exception_handler, http_exception_handler, validation_exception_handler,
)
from backend.core.logging import setup_logging

log = logging.getLogger("civicconnect.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup / shutdown lifecycle."""
    setup_logging()
    log.info("CivicConnect v2 API starting up...")
    # Bootstrap Redis consumer groups (safe to call if Redis is offline)
    try:
        from backend.events import ensure_consumer_groups, start_background_workers
        ensure_consumer_groups()
        start_background_workers()
        log.info("Redis event system initialised.")
    except Exception as exc:
        log.warning("Event system startup skipped: %s", exc)
    yield
    log.info("CivicConnect v2 API shutting down.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    description="Backend API for CivicConnect v2",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# Custom exception handler
app.add_exception_handler(CivicConnectException, civicconnect_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Include v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.PROJECT_NAME}"}
