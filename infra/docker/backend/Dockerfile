# CivicConnect backend API. Build from the repository root (the compose file does this):
#   docker build -f infra/docker/backend/Dockerfile -t civicconnect-backend:local .
# Same Python as the development venv (3.13.6). Runs as a non-root user; on start it applies the migrations and then serves the API.
# INSTALL_S3=1 adds boto3 (backend/requirements-s3.txt) for STORAGE_BACKEND=s3.
ARG PYTHON_VERSION=3.13.6
FROM python:${PYTHON_VERSION}-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY backend/requirements.txt backend/requirements-s3.txt backend/
ARG INSTALL_S3=0
RUN pip install -r backend/requirements.txt \
    && if [ "$INSTALL_S3" = "1" ]; then pip install -r backend/requirements-s3.txt; fi

# The code runs from /app (the working directory first on sys.path), exactly like the development runs: backend/, ai/ (inference + the demo-city data the seed reads), alembic/.
COPY alembic.ini ./
COPY alembic alembic
COPY backend backend
COPY ai ai

RUN useradd --system --uid 10001 --create-home app \
    && mkdir -p /data/media \
    && chown -R app:app /data
USER app

ENV MEDIA_DIR=/data/media
VOLUME /data/media
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/ready', timeout=4).status == 200 else 1)"]

CMD ["sh", "-c", "python -m alembic upgrade head && exec python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
