"""Fixtures for the database-backed API tests. Everything runs on a fresh SQLite FILE database per test (separate connections, so "commit before the AI reads" is
really exercised); the PostgreSQL / PostGIS checks live in test_postgres_integration.py and run only when TEST_DATABASE_URL is set."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import pytest

from backend.core.security import create_access_token, get_password_hash

_PW = "correct-horse-battery"
_PW_HASH = get_password_hash(_PW)


@pytest.fixture(autouse=True)
def _no_redis_waits():
    """Tests never wait for a Redis connection timeout: the publisher is told Redis is down (test_events.py manages its own state)."""
    import backend.events.publisher as pub
    saved = (pub._redis_client, pub._redis_down_until)
    pub._redis_client, pub._redis_down_until = None, time.monotonic() + 1e6
    yield
    pub._redis_client, pub._redis_down_until = saved


@dataclass
class Env:
    session_factory: object
    client: object
    users: dict = field(default_factory=dict)

    def make_user(self, role: str, key: str | None = None, *, department_id: str | None = None, ward_id: str | None = None, email: str | None = None, name: str | None = None):
        from backend.models import User
        key = key or role
        with self.session_factory() as db:
            u = User(name=name or key, email=email or f"{key}@example.test", hashed_password=_PW_HASH, role=role, department_id=department_id, ward_id=ward_id)
            db.add(u)
            db.commit()
            self.users[key] = {"id": u.id, "role": role, "email": u.email}
        return self.users[key]

    def headers(self, key: str) -> dict:
        u = self.users[key]
        return {"Authorization": f"Bearer {create_access_token(u['id'], u['role'])}"}

    def idem(self, key: str, k: str | None = None) -> dict:
        import uuid
        return {**self.headers(key), "Idempotency-Key": k or str(uuid.uuid4())}


@pytest.fixture
def password() -> str:
    return _PW


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Fresh database + reference data (departments, wards) + local media store + the SQL-backed AI gateway (no AI provider: rules and local models only)."""
    from fastapi.testclient import TestClient

    from backend.ai_gateway import configure_gateway
    from backend.core.config import settings
    from backend.db import session as dbs
    from backend.main import app
    from backend.models import Base
    from backend.services import auth as auth_service
    from backend.services import seed
    from backend.storage import LocalStorage, set_storage

    original_url = str(dbs.engine.url)
    dbs.configure_database(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(dbs.engine)
    with dbs.SessionLocal() as db:
        seed.seed_reference(db)
        db.commit()
    set_storage(LocalStorage(tmp_path / "media"))
    auth_service.reset_throttle()
    monkeypatch.setattr(settings, "AI_GATEWAY_STORE", "sql")
    for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "CLOUDFLARE_API_TOKEN", "AI_LOCAL_CLASSIFIER_PATH", "AI_TEXT_ONNX_PATH", "AI_EMBED_ONNX_PATH",
              "AI_VISION_ONNX_PATH", "AI_FUSION_WEIGHTS_PATH", "AI_FUSION_EMBEDDING_WEIGHTS_PATH", "AI_ROUTES"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr("backend.ai_gateway.envfile.load_env_file", lambda *a, **k: [])
    from backend.ai_gateway.sql import build_sql_gateway
    configure_gateway(build_sql_gateway())
    e = Env(session_factory=dbs.SessionLocal, client=TestClient(app, raise_server_exceptions=False))
    yield e
    configure_gateway(None)
    set_storage(None)
    dbs.configure_database(original_url)


@pytest.fixture
def staffed(env):
    """The cast of a small city: citizens, an operator + worker per department, a ward officer, administrators and an overlooker."""
    env.make_user("citizen", "alice")
    env.make_user("citizen", "bob")
    env.make_user("operator", "roads_op", department_id="road_maintenance")
    env.make_user("operator", "water_op", department_id="water_supply")
    env.make_user("department_manager", "roads_mgr", department_id="road_maintenance")
    env.make_user("field_worker", "roads_worker", department_id="road_maintenance")
    env.make_user("field_worker", "water_worker", department_id="water_supply")
    env.make_user("city_admin", "admin")
    env.make_user("overlooker", "overlooker")
    from backend.models import Ward
    with env.session_factory() as db:
        w = db.query(Ward).filter(Ward.label == "W01").first() or db.query(Ward).first()
        env.ward_id = w.id
        lat, lon = w.centroid_lat, w.centroid_lon
    env.make_user("ward_officer", "ward_officer", ward_id=env.ward_id)
    env.where = {"latitude": lat, "longitude": lon}
    return env
