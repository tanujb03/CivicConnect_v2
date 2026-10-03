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
* **scan**: only the daemon. No backend code talks to clamd yet (migration 0003 added the evidence scan columns, nothing writes them); point a future scan worker at `clamav:3310` (or `localhost:3310`).
* **obs**: only the collector and UI. The backend has no OpenTelemetry instrumentation yet, so Jaeger stays empty until an exporter is added (OTLP endpoint `http://jaeger:4318`).

## Verified on this machine (2026-10-04, 24 GB RAM, WSL2 limit 10 GB)

All profiles start. Core from empty volumes: `up --wait` healthy, `alembic upgrade head` (0003), `seed_demo` (8 departments, 10 wards, 560 cases), `/api/v1/health/ready` = ready with `vector_search: true`, process runs as uid 10001, evidence init/PUT/complete/GET round trip with the signed URLs. `s3`: bucket created, a full round trip through `S3Storage` with boto3 against SeaweedFS (the first time `S3Storage` ran against a live server; it was done from inside the compose network). `scan`: healthy after 22 s, clamd answers `PING` and flags the EICAR test string over `INSTREAM`. `obs`: UI answers on 16686, OTLP HTTP 4318 answers, OTLP gRPC 4317 accepts TCP connections (no spans were sent).

Not verified: image tags for `jaeger`, `seaweedfs` and `aws-cli` float (`latest`), so a later pull may behave differently (observed: SeaweedFS 4.48, aws-cli 2.37.9; the Jaeger version was not read); starting with `--profile s3` and the real `STORAGE_BACKEND=s3` path from a phone; a cold ClamAV start with an empty signature volume while offline; behaviour on Python 3.14 or another host OS.
