import os
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "CHANGE_THIS_IN_PRODUCTION_TO_A_SECURE_RANDOM_STRING"


class Settings(BaseSettings):
    PROJECT_NAME: str = "CivicConnect v2 API"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "dev"                     # "prod" refuses to start with the development secret

    # Database. ``DATABASE_URL`` (any SQLAlchemy URL; tests use sqlite) wins over the POSTGRES_* parts.
    DATABASE_URL: Optional[str] = None
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "civicconnect"
    POSTGRES_PORT: str = "5432"

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Auth
    SECRET_KEY: str = DEV_SECRET
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    DEMO_PASSWORD: str = "civicconnect-demo"     # password of the seeded demo accounts (python -m backend.scripts.seed_demo); development only

    # Redis (events / jobs). The API works without it: events are skipped and logged.
    REDIS_URL: str = "redis://localhost:6379/0"

    # Rate limiting (WP3): Redis counters with an in-process fallback. Off when RATE_LIMIT_ENABLED=false (the unit tests) or ENVIRONMENT=test.
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_LOGIN_IP_PER_MIN: int = 10
    RATE_LIMIT_LOGIN_IDENTIFIER_PER_MIN: int = 5
    RATE_LIMIT_REGISTER_IP_PER_MIN: int = 5
    RATE_LIMIT_CASE_CREATE_PER_HOUR: int = 20
    RATE_LIMIT_UPLOAD_INIT_PER_HOUR: int = 60
    RATE_LIMIT_AI_PER_HOUR: int = 30                 # intake/fusion/triage analyze and copilot: protects the free-tier provider quotas
    RATE_LIMIT_DEFAULT_PER_MIN: int = 600            # every other route, per user (per IP when anonymous)
    RATE_LIMIT_TRUST_FORWARDED_FOR: bool = False     # true only behind a proxy or tunnel you control: the client IP is then the RIGHTMOST X-Forwarded-For entry. Left false behind a
                                                     # tunnel, every phone shares the tunnel's address and so the per-IP login (10/min) and register (5/min) limits

    # Expo push (WP5): notifications of users with a registered device are sent through Expo's push service (free). The access token is optional (enhanced security mode).
    EXPO_PUSH_URL: str = "https://exp.host/--/api/v2/push/send"
    EXPO_RECEIPTS_URL: str = "https://exp.host/--/api/v2/push/getReceipts"
    EXPO_ACCESS_TOKEN: Optional[str] = None          # secret: never logged
    PUSH_BATCH_SIZE: int = 100                        # Expo accepts at most 100 messages per request
    PUSH_MAX_ATTEMPTS: int = 3
    PUSH_WORKER_INTERVAL_S: float = 5.0
    PUSH_MAX_DEVICES_PER_USER: int = 10               # registering an 11th active token revokes the user's least recently seen one

    # Upload malware scan (WP6): ClamAV's clamd over TCP (INSTREAM). Off by default; then new evidence is marked UNSCANNED.
    SCAN_ENABLED: bool = False
    CLAMD_HOST: str = "localhost"
    CLAMD_PORT: int = 3310
    SCAN_MAX_BYTES: int = 25 * 1024 * 1024            # larger files are not sent to clamd (status ERROR)
    SCAN_TIMEOUT_S: float = 30.0
    SCAN_MAX_ATTEMPTS: int = 3
    SCAN_WORKER_INTERVAL_S: float = 5.0

    # OpenTelemetry (WP8): tracing is off by default; with OTEL_ENABLED=true spans go to an OTLP/HTTP collector (Jaeger: http://localhost:4318, in compose http://jaeger:4318)
    OTEL_ENABLED: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4318"

    # Browser origins allowed to call the API (comma separated); "*" only for local experiments
    CORS_ORIGINS: str = ("http://localhost:5173,http://localhost:5174,http://localhost:5175,http://localhost:3000,http://localhost:4173,"
                          "http://localhost:8080,http://localhost:8081,http://localhost:8082,http://localhost:19006")      # Vite apps, admin / overlooker (8080), Expo web (8081, 19006)

    # Evidence / media (design §44): private storage, generated object keys, short-lived signed URLs
    STORAGE_BACKEND: str = "local"               # "local" (files under MEDIA_DIR, signed URLs served by this API) or "s3" (MinIO / Supabase / any S3-compatible)
    MEDIA_DIR: str = "./media"
    PUBLIC_BASE_URL: str = "http://localhost:8000"   # how clients reach this API (used inside signed local URLs)
    SIGNED_URL_TTL_SECONDS: int = 900
    MAX_UPLOAD_BYTES: int = 25 * 1024 * 1024
    S3_ENDPOINT_URL: Optional[str] = None
    S3_BUCKET: str = "civicconnect-evidence"
    S3_ACCESS_KEY: Optional[str] = None
    S3_SECRET_KEY: Optional[str] = None
    S3_REGION: str = "us-east-1"

    # Which store the AI gateway reads cases from: "sql" (the database; the default, the API's SQL paths need it) or "demo" (the synthetic demo city, no database needed)
    AI_GATEWAY_STORE: str = "sql"

    # .env also carries AI keys/model ids that are not backend settings. CIVIC_IGNORE_ENV_FILE=1 (set by the root conftest.py) makes the process ignore it, so a developer's
    # .env (e.g. real API keys) can never change what the tests do.
    model_config = SettingsConfigDict(env_file=None if os.environ.get("CIVIC_IGNORE_ENV_FILE") else ".env", case_sensitive=True, extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
