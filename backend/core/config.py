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

    # Browser origins allowed to call the API (comma separated); "*" only for local experiments
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5174,http://localhost:5175,http://localhost:3000,http://localhost:4173"

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

    # Which store the AI gateway reads cases from: "sql" (the database) or "demo" (the synthetic demo city, no database needed)
    AI_GATEWAY_STORE: str = "demo"

    # .env also carries AI keys/model ids that are not backend settings. CIVIC_IGNORE_ENV_FILE=1 (set by the root conftest.py) makes the process ignore it, so a developer's
    # .env (e.g. AI_GATEWAY_STORE=sql, real API keys) can never change what the tests do.
    model_config = SettingsConfigDict(env_file=None if os.environ.get("CIVIC_IGNORE_ENV_FILE") else ".env", case_sensitive=True, extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
