# Docker Compose stack

`infra/compose/docker-compose.yml` runs the backend with its own PostgreSQL (18.6 + PostGIS 3.6 + pgvector 0.8.6, built from `infra/docker/postgres`), Redis and optional services behind profiles. It is separate from the day-to-day dev setup (`scripts\dev\db_up.ps1`: containers `civic-db` on 5433 and `civic-redis` on 6379), so the default host ports differ and the two can run at the same time.

```powershell
# from the repository root (a lane: set API_PORT to its port, e.g. $env:API_PORT = "8002")
docker compose --env-file .env -f infra/compose/docker-compose.yml up -d --build --wait        # db + redis + backend (migrations run on start)
docker compose -f infra/compose/docker-compose.yml exec backend python -m backend.scripts.seed_demo   # reference data + 560 synthetic cases + demo accounts
curl http://localhost:8000/api/v1/health/ready                                                   # {"status":"ready","checks":{"database":"ok","storage":"ok","redis":"ok"},...}
docker compose -f infra/compose/docker-compose.yml down -v                                       # stop and DROP the compose volumes (down without -v keeps the data)
```

`--env-file .env` is optional: it feeds the variables listed under the compose section of `.env.example` (names only; secrets stay in the gitignored `.env`) and, through `env_file`, the AI keys and model ids reach the backend container. Without it everything runs on defaults.

The backend image (`infra/docker/backend/Dockerfile`) is `python:3.13.6-slim` (the venv's Python), installs `backend/requirements.txt`, runs as the non-root user `app` (uid 10001), and starts with `alembic upgrade head` followed by `uvicorn` on port 8000. Its build context is the repository root; `.dockerignore` keeps `apps/`, `packages/`, `docs/`, tests, training code and every `.env*` out of it. The media volume is `/data/media`. `PUBLIC_BASE_URL` defaults to `http://localhost:${API_PORT}`; for phones see `docs/infra/TUNNEL.md`.

## Services, ports and memory

`mem_limit` is the cap compose sets; "measured" is `docker stats` idle on 2026-10-04 (Docker 29.2.1, Compose 5.0.2). All limits together are 6.5 GB, measured use about 1.2 GB.

| Service (profile) | Image | Host port | mem_limit | Measured idle | Notes |
|---|---|---|---:|---:|---|
| `db` (always) | `civicconnect-postgres:local` | 5434 (`COMPOSE_DB_PORT`) | 1 GB | 31 MB | Volume `pgdata` mounted at `/var/lib/postgresql` (PostgreSQL 18 layout). |
| `redis` (always) | `redis:7` (7.4.11) | 6380 (`COMPOSE_REDIS_PORT`) | 256 MB | 6 MB | No persistence, `maxmemory 128mb`. |
| `backend` (always) | `civicconnect-backend:local` | 8000 (`API_PORT`) | 1 GB | 117 MB | Image 658 MB. Healthcheck: `GET /api/v1/health/ready`. |
| `s3`, `s3-init` (`s3`) | `chrislusf/seaweedfs`, `amazon/aws-cli` | 8333 (`COMPOSE_S3_PORT`) | 512 MB, 256 MB | 66 MB | S3-compatible store; `s3-init` creates the bucket once and exits. |
| `clamav` (`scan`) | `clamav/clamav:stable` (ClamAV 1.5.4) | 3310 (`COMPOSE_CLAMD_PORT`) | 3 GB | 952 MB | clamd loads the signatures into RAM and needs about double that while it reloads them, hence the 3 GB cap. Volume `clamav-db` keeps the signatures. |
| `jaeger` (`obs`) | `jaegertracing/all-in-one` | 16686 (UI), 4317 (OTLP gRPC), 4318 (OTLP HTTP) | 512 MB | 10 MB | In-memory storage, at most 20000 traces. OTLP is enabled (`COLLECTOR_OTLP_ENABLED`). |

Start a profile by adding `--profile <name>` (repeatable) to `up`:

```powershell
docker compose -f infra/compose/docker-compose.yml --profile scan --profile obs up -d --wait
# S3 storage: the backend needs boto3 in the image and the s3 backend selected
$env:INSTALL_S3 = "1"; $env:STORAGE_BACKEND = "s3"
docker compose -f infra/compose/docker-compose.yml --profile s3 up -d --build --wait
```

## What each profile does for the application today

* **s3**: `STORAGE_BACKEND=s3` works with it (`S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` are set for compose). The pre-signed URLs carry the endpoint host, `http://s3:8333` inside the compose network, which a phone cannot reach; for a phone set `S3_ENDPOINT_URL` to an address both the backend container and the phone can reach (for example `http://<LAN IP>:8333`). MinIO is **not** used: its images are no longer published (`docker.io/minio/minio` does not exist, `quay.io/minio/minio` answers 401), so SeaweedFS stands in; it has no accounts configured, so any key pair is accepted (development only).
* **scan**: the ClamAV daemon. The backend scans uploads when it runs with `SCAN_ENABLED=true` (compose passes `SCAN_ENABLED`, default false, and `CLAMD_HOST`, default `clamav`): `$env:SCAN_ENABLED = "true"; docker compose -f infra/compose/docker-compose.yml --profile scan up -d --wait`. Uploads then start `PENDING` and a download is refused until the file is `CLEAN`. Detection was verified against this daemon on 2026-10-09 (see below).
* **obs**: the collector and UI. The backend exports traces to it when `OTEL_ENABLED=true` (off by default). **OpenTelemetry is only activated when `OTEL_ENABLED=true`; there is no guarantee that no `opentelemetry` module is imported while it is off** (FastAPI and redis-py import parts of it themselves): while off, no tracer provider, exporter or instrumentation is installed. Parentless background HTTP spans, for example the Expo push sends, are not traced.
  * Jaeger UI: **http://localhost:16686**, service `civicconnect-backend`. OTLP/HTTP is on 4318: set `OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318` for the backend inside compose, `http://localhost:4318` (the default) when the API runs on the host. The value is a base URL; the exporter posts to `<base>/v1/traces`. `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` is used verbatim if set. `OTEL_SERVICE_NAME` overrides the service name, `OTEL_TRACES_SAMPLER` / `OTEL_TRACES_SAMPLER_ARG` the sampling.
  * One request is one trace: the FastAPI server span, SQLAlchemy / Redis / httpx client spans, the Redis stream publish span and the worker's consumer span (trace context travels in the `traceparent` / `tracestate` fields of the stream message). Client spans (SQL, Redis, httpx) without a parent are dropped on purpose (sampler): HTTP calls made by background threads with no request behind them (the Expo push sends, scan-worker calls, XACKs, XREADGROUP polls, startup queries) are **not traced by design**; work done inside a stream handler is, because the consumer span is its parent.
  * **Query strings are redacted before export.** A span processor in front of the exporter rewrites `url.query`, `url.full`, `http.url`, `http.target` and `url.path`: parameter names stay, every value becomes `REDACTED` (`q=REDACTED&limit=REDACTED`), passwords inside URLs and fragments too. So an admin search `?q=<name or e-mail>` or coordinates never reach Jaeger. SQL spans carry placeholders and Redis arguments are sanitised by the instrumentation (both asserted in `test_telemetry.py`). Not scrubbed: exception messages recorded on spans.
  * The batch span processor is not fork-safe: run one uvicorn process per container (or create the provider per worker process, which `setup_telemetry()` does when called from the lifespan) and never use `--preload`. OpenTelemetry cannot be restarted inside one process after `shutdown_telemetry()` (a second `setup_telemetry()` raises `TelemetryUnavailable`; restart the process).
  * In compose, put `OTEL_ENABLED=true` and `OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318` in the root `.env` (the `backend` service reads it through `env_file`), then `docker compose -f infra/compose/docker-compose.yml --profile obs up -d --wait`. Without the `obs` profile the exporter just fails to connect (logged, no effect on requests).
  * Where each variable is read: `OTEL_ENABLED` and `OTEL_EXPORTER_OTLP_ENDPOINT` from the process environment or, through `Settings`, from the repo's environment file. `OTEL_SERVICE_NAME`, `OTEL_TRACES_SAMPLER`, `OTEL_TRACES_SAMPLER_ARG`, `OTEL_RESOURCE_ATTRIBUTES` and `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` are read from the **real process environment only** (the environment file does not export them; in compose they must be in the `backend` service's `environment:`).

## Tracing verified against a real Jaeger (2026-10-09)

The image `jaegertracing/all-in-one:latest` (the `obs` profile's image) was run with `docker run` on 16686 and 4318 instead of through compose, and the API ran on the host (`OTEL_ENABLED=true`, `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318`, dev database, real Redis). One `POST /api/v1/cases` by a demo citizen produced **one trace of 101 spans in service `civicconnect-backend`**: the request root span (`POST /api/v1/cases`, 253 ms), 89 database spans (INSERT / SELECT / UPDATE / SAVEPOINT), the Redis `XADD`, three `civic:ai_jobs publish` spans (children of `fastapi.endpoint`) and three `civic:ai_jobs process` spans (the worker, children of the publish spans, so the trace context crossed the Redis stream), and the outbound Gemini calls (`POST .../openai/embeddings` and `.../chat/completions`; the query string is redacted). Not verified: the compose `obs` profile itself with the backend as a container, a trace spanning two processes (here the worker runs in the API process), and Jaeger retention beyond in-memory use.

## Core stack from empty volumes, end to end (2026-10-09)

Project name `civicsmoke` (`docker compose -p civicsmoke ...`) so nothing touches the dev containers `civic-db` / `civic-redis`, which carry the same image labels as the compose `db` service. With `SCAN_ENABLED=true` and `--profile scan`: `up -d --build --wait` **67 s** (cached base images; db, redis, clamav and backend all healthy), `alembic current` = `0004 (head)`, `seed_demo` 5 s (8 departments, 10 wards, 560 cases), then `python scripts/dev/smoke.py --no-ai --scan`: **42 passed, 0 failed in 12 s**; the same run through the laptop's Wi-Fi address with `PUBLIC_BASE_URL=http://10.10.90.240:8000` also passed 42 of 42 (signed upload and download URLs carry the LAN host). The real clamd test `backend/tests/test_malware_scan.py::test_eicar_against_a_real_clamd` ran for the first time and passed. clamd flags only the plain EICAR file (`Eicar-Test-Signature`), not EICAR behind a JPEG header; the API's magic-byte check rejects plain EICAR in an image upload before the scanner sees it (`EVIDENCE_REJECTED`), so the smoke test asserts that refusal plus a clean upload ending `CLEAN`. `down -v` was not run (the guard hook blocks it and the volumes were already empty); the project was stopped with `down`, its volumes `civicsmoke_*` remain. **Idle memory** 75 s after the stack was healthy (`docker stats`, no traffic): backend 97 MiB, db 34 MiB, redis 3.5 MiB, clamav 949 MiB (the signature database; the other three together are about 135 MiB). Counts re-measured the same day: 78 API operations on 66 paths, one Alembic head `0004`, full suite 1621 passed / 5 skipped. Not verified: a phone, a Cloudflare Tunnel (`cloudflared` is not installed), the `s3` profile with the current code.

## Verified on this machine (2026-10-04, 24 GB RAM, WSL2 limit 10 GB)

All profiles start. Core from empty volumes: `up --wait` healthy, `alembic upgrade head` (0003), `seed_demo` (8 departments, 10 wards, 560 cases), `/api/v1/health/ready` = ready with `vector_search: true`, process runs as uid 10001, evidence init/PUT/complete/GET round trip with the signed URLs. `s3`: bucket created, a full round trip through `S3Storage` with boto3 against SeaweedFS (the first time `S3Storage` ran against a live server; it was done from inside the compose network). `scan`: healthy after 22 s, clamd answers `PING` and flags the EICAR test string over `INSTREAM`. `obs`: UI answers on 16686, OTLP HTTP 4318 answers, OTLP gRPC 4317 accepts TCP connections (no spans were sent).

Not verified: image tags for `jaeger`, `seaweedfs` and `aws-cli` float (`latest`), so a later pull may behave differently (observed: SeaweedFS 4.48, aws-cli 2.37.9; the Jaeger version was not read); starting with `--profile s3` and the real `STORAGE_BACKEND=s3` path from a phone; a cold ClamAV start with an empty signature volume while offline; behaviour on Python 3.14 or another host OS.
