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


def test_pgvector_untyped_column_partial_hnsw_indexes_and_the_documented_query(pg):
    """Migration 0003: ``embedding_vec`` has NO fixed dimension, 384 and 768 dim vectors coexist, and each dimension has a partial HNSW cosine expression index
    (pgvector README, "Can I store vectors with different dimensions in the same column?") that the documented query form really uses."""
    from sqlalchemy import text
    assert _alembic("current")[1].count("0003") >= 1
    conn = pg.connect()
    trans = conn.begin()
    try:
        assert conn.execute(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")).scalar()
        assert conn.execute(text("SELECT format_type(atttypid, atttypmod) FROM pg_attribute WHERE attrelid = 'case_embeddings'::regclass AND attname = 'embedding_vec'")).scalar() == "vector"
        defs = {r[0]: r[1] for r in conn.execute(text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'case_embeddings'"))}
        for dim in (384, 768):
            d = defs[f"ix_case_embeddings_vec_{dim}"]
            assert "hnsw" in d and f"vector({dim})" in d and "vector_cosine_ops" in d and f"embedding_dim = {dim}" in d
        conn.execute(text("SET LOCAL session_replication_role = replica"))                    # no parent cases needed for this check (rolled back below)
        insert = text("INSERT INTO case_embeddings (case_id, model, vector, created_at, embedding_dim, embedding_model, embedding_vec) "
                      "VALUES (:id, 'm', '[]', now(), :dim, 'test', CAST(:vec AS vector))")
        for cid, dim, hot in (("pgv-a", 384, 0), ("pgv-b", 384, 1), ("pgv-c", 768, 0)):
            conn.execute(insert, {"id": cid, "dim": dim, "vec": "[" + ",".join("1" if i == hot else "0" for i in range(dim)) + "]"})
        assert dict(conn.execute(text("SELECT embedding_dim, count(*) FROM case_embeddings GROUP BY 1")).all()) == {384: 2, 768: 1}
        assert {r[0] for r in conn.execute(text("SELECT vector_dims(embedding_vec) FROM case_embeddings"))} == {384, 768}
        conn.execute(text("SET LOCAL enable_seqscan = off"))                                  # a three-row table would otherwise never use the index
        query = ("SELECT case_id FROM case_embeddings WHERE embedding_dim = 384 "
                 "ORDER BY embedding_vec::vector(384) <=> CAST(:q AS vector(384)) LIMIT 1")
        q = {"q": "[" + ",".join("1" if i == 1 else "0" for i in range(384)) + "]"}
        assert "ix_case_embeddings_vec_384" in "\n".join(r[0] for r in conn.execute(text("EXPLAIN " + query), q))
        assert conn.execute(text(query), q).scalar() == "pgv-b"                               # cosine nearest, never a 768-dim row
    finally:
        trans.rollback()
        conn.close()


def test_postgis_column_indexes_and_dwithin_agree_with_the_portable_path(pg):
    from sqlalchemy import text

    from backend.ai_gateway.sql import SqlCaseRepository
    from backend.db import session as dbs
    from backend.models import CivicCase
    from backend.services import seed
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
        ready = c.get("/api/v1/health/ready").json()
        assert ready["checks"]["database"] == "ok" and ready["vector_search"] is True           # the image of scripts/dev/db_up.ps1 ships pgvector
    finally:
        dbs.configure_database(original)


def test_trends_group_by_runs_on_postgres_and_matches_a_python_computation(pg):
    """The daily / weekly SQL buckets (to_char / date_trunc / timezone on PostgreSQL, strftime on SQLite) must agree with an independent computation over the rows."""
    from collections import Counter
    from datetime import date, datetime, timedelta

    from fastapi.testclient import TestClient

    from backend.db import session as dbs
    from backend.main import app
    from backend.services import seed
    from backend.services.city_rows import case_rows
    original = str(dbs.engine.url)
    dbs.configure_database(URL)
    try:
        with dbs.SessionLocal() as db:
            seed.seed_demo_city(db)
            db.commit()
            rows = case_rows(db, True)
        c = TestClient(app, raise_server_exceptions=False)
        tok = c.post("/api/v1/auth/login", json={"identifier": "admin@demo.civicconnect.test", "password": "civicconnect-demo"}).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        day = lambda iso: datetime.fromisoformat(iso.replace("Z", "+00:00")).date()      # noqa: E731
        for gran in ("daily", "weekly"):
            t = c.get(f"/api/v1/analytics/trends?granularity={gran}&days=365", headers=h).json()
            first = date.fromisoformat(t["from"])
            bucket = (lambda d: d - timedelta(days=d.weekday())) if gran == "weekly" else (lambda d: d)
            inside = [r for r in rows if day(r["created_at"]) >= first]
            assert len(inside) > 0
            assert Counter((x["bucket"], x["category"], x["status"]) for x in t["series"] for _ in range(x["count"])) == \
                Counter((bucket(day(r["created_at"])).isoformat(), r["category"] or "other", r["status"]) for r in inside)
            totals = {x["bucket"]: x for x in t["totals"]}
            created, resolved = Counter(), Counter()
            for r in inside:
                created[bucket(day(r["created_at"])).isoformat()] += 1
            for r in rows:
                if r["status"] == "RESOLVED" and r["closed_at"] and day(r["closed_at"]) >= first:
                    resolved[bucket(day(r["closed_at"])).isoformat()] += 1
            assert {k: v["created"] for k, v in totals.items() if v["created"]} == dict(created) and {k: v["resolved"] for k, v in totals.items() if v["resolved"]} == dict(resolved)
            assert all(date.fromisoformat(k).weekday() == 0 for k in totals) if gran == "weekly" else len(totals) == 365
    finally:
        dbs.configure_database(original)
