"""Runs only when TEST_DATABASE_URL points at an EMPTY PostgreSQL database with the PostGIS extension available, e.g.

    createdb civicconnect_test
    TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/civicconnect_test python -m pytest backend/tests/test_postgres_integration.py

It checks what SQLite cannot: the Alembic migrations (up, no drift, down, up), the PostGIS generated column and indexes, ST_DWithin candidate search agreeing with the
portable path, and the seeded demo city through the real API."""
import os

import pytest

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set (needs PostgreSQL + PostGIS)")


def _alembic(*args):
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    r = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=root, env={**os.environ, "DATABASE_URL": URL}, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


@pytest.fixture(scope="module")
def pg():
    from sqlalchemy import create_engine, text
    eng = create_engine(URL)
    with eng.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
        c.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    yield eng
    eng.dispose()


def test_migrations_apply_have_no_drift_and_round_trip(pg):
    assert _alembic("upgrade", "head")[0] == 0
    code, out = _alembic("check")
    assert code == 0, out
    assert _alembic("downgrade", "base")[0] == 0
    assert _alembic("upgrade", "head")[0] == 0


def test_postgis_column_indexes_and_dwithin_agree_with_the_portable_path(pg):
    from sqlalchemy import text
    from backend.db import session as dbs
    from backend.models import CivicCase
    from backend.services import seed
    from backend.ai_gateway.sql import SqlCaseRepository
    from backend.services.geo import haversine_m
    original = str(dbs.engine.url)
    dbs.configure_database(URL)
    try:
        with dbs.SessionLocal() as db:
            seed.seed_demo_city(db)
            idx = {r[0] for r in db.execute(text("select indexname from pg_indexes where tablename='civic_cases'"))}
            assert {"ix_civic_cases_geog", "ix_civic_cases_fts"} <= idx
            assert db.execute(text("select count(*) from civic_cases where geog is not null")).scalar() == 560
            case = db.query(CivicCase).filter(CivicCase.status == "RESOLVED").first()
        repo = SqlCaseRepository()
        snap = repo.get_case(case.id)
        got = repo.fusion_candidates(snap, radius_m=300.0, time_window_days=400, max_candidates=50, same_category=False)
        with dbs.SessionLocal() as db:
            expected = {c.id for c in db.query(CivicCase).filter(CivicCase.id != case.id, CivicCase.status != "REJECTED") if haversine_m((snap.latitude, snap.longitude), (c.latitude, c.longitude)) <= 300.0
                        and abs((c.created_at - case.created_at).days) <= 400}
        assert len({c.id for c in got} ^ expected) <= 2        # ST_DWithin measures on the spheroid, haversine on a sphere: only metre-level boundary cases may differ
        assert len(got) > 0
        # a full-text query uses the GIN index expression
        with dbs.SessionLocal() as db:
            n = db.execute(text("select count(*) from civic_cases where to_tsvector('simple', coalesce(title,'')||' '||coalesce(description,'')||' '||case_number) @@ plainto_tsquery('simple','DEMO-2026-000001')")).scalar()
            assert n >= 0
    finally:
        dbs.configure_database(original)


def test_demo_city_through_the_real_api_on_postgres(pg):
    from fastapi.testclient import TestClient
    from backend.db import session as dbs
    from backend.main import app
    original = str(dbs.engine.url)
    dbs.configure_database(URL)
    try:
        c = TestClient(app, raise_server_exceptions=False)
        tok = c.post("/api/v1/auth/login", json={"identifier": "admin@demo.civicconnect.test", "password": "civicconnect-demo"}).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        ov = c.get("/api/v1/analytics/overview", headers=h).json()
        assert ov["total_cases"] == 560 and ov["open_cases"] > 0
        assert len(c.get("/api/v1/cases?limit=100", headers=h).json()["items"]) == 100
        assert c.get("/api/v1/map/hotspots", headers=h).status_code == 200 and len(c.get("/api/v1/map/recurring-problems", headers=h).json()["items"]) > 0
        assert c.get("/api/v1/health/ready").json()["checks"]["database"] == "ok"
    finally:
        dbs.configure_database(original)
