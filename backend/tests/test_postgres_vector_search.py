"""AI-2 candidate search and embedding storage on PostgreSQL + PostGIS + pgvector (runs only when TEST_DATABASE_URL points at a database where the schema may be dropped).

Checks: ``save_embedding`` fills the JSON vector AND ``embedding_vec`` / ``embedding_dim`` / ``embedding_model``; the deterministic gate (category, ST_DWithin, time window) comes first;
candidates are ordered by cosine distance in SQL with the SAME cast expression as the partial HNSW index of migration 0003 (``embedding_vec::vector(D) <=> CAST(:q AS vector(D))``
with ``embedding_dim = D``), limit 50, comparing only vectors of the same model and dimension; and the result equals the Python path used on SQLite / without the extension."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, text

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set (needs PostgreSQL + PostGIS + pgvector)")
LAT, LON = 19.0760, 72.8777


def unit(dim: int, hot: int, other: int | None = None, mix: float = 0.0) -> list[float]:
    v = [0.0] * dim
    v[hot] = 1.0
    if other is not None:
        v[other] = mix
    n = sum(x * x for x in v) ** 0.5
    return [x / n for x in v]


@pytest.fixture(scope="module")
def pg():
    from backend.db import session as dbs
    eng = create_engine(URL)
    with eng.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
        c.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    root = Path(__file__).resolve().parents[2]
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=root, env={**os.environ, "DATABASE_URL": URL}, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    original = str(dbs.engine.url)
    dbs.configure_database(URL)
    yield eng
    dbs.configure_database(original)
    eng.dispose()


@pytest.fixture
def repo(pg):
    from backend.ai_gateway.sql import SqlCaseRepository
    from backend.db import session as dbs
    with dbs.SessionLocal() as db:
        db.execute(text("DELETE FROM case_embeddings"))
        db.execute(text("DELETE FROM civic_cases"))
        db.commit()
    return SqlCaseRepository()


def cases(*specs):
    """specs: (name, d_lat, category, age_days) -> {name: id}"""
    from backend.db import session as dbs
    from backend.tests.test_ai_embeddings import make_case
    with dbs.SessionLocal() as db:
        ids = {n: make_case(db, LAT + d, LON, category=cat, age_days=age).id for n, d, cat, age in specs}
        db.commit()
    return ids


def search(repo, subject, **kw):
    snap = repo.get_case(subject)
    return snap, repo.fusion_candidates(snap, **{**dict(radius_m=300.0, time_window_days=30, max_candidates=50, same_category=True), **kw})


def test_save_embedding_fills_the_json_vector_and_every_pgvector_column(pg, repo):
    from backend.db import session as dbs
    [cid] = cases(("a", 0.0, "roads", 1)).values()
    assert repo.save_embedding(cid, unit(384, 3), "m7@1") == {"dim": 384, "model": "m7@1", "pgvector": True}
    with dbs.SessionLocal() as db:
        row = db.execute(text("SELECT model, embedding_model, embedding_dim, jsonb_array_length(vector), vector_dims(embedding_vec), embedding_vec::vector(384) <=> CAST(:q AS vector(384)) "
                              "FROM case_embeddings WHERE case_id = :id"), {"id": cid, "q": str(unit(384, 3))}).one()
    assert tuple(row[:5]) == ("m7@1", "m7@1", 384, 384, 384) and row[5] == pytest.approx(0.0, abs=1e-6)
    assert repo.save_embedding(cid, unit(768, 5), "m7@2")["dim"] == 768                           # re-embedding with another model / dimension replaces every column
    with dbs.SessionLocal() as db:
        assert tuple(db.execute(text("SELECT embedding_model, embedding_dim, vector_dims(embedding_vec) FROM case_embeddings WHERE case_id = :id"), {"id": cid}).one()) == ("m7@2", 768, 768)


def test_pgvector_orders_the_gated_set_by_cosine_and_only_compares_same_model_and_dimension(pg, repo):
    ids = cases(("subject", 0.0, "roads", 1), ("close", 0.0002, "roads", 1), ("orthogonal", 0.0003, "roads", 1), ("opposite", 0.0004, "roads", 1), ("other_model", 0.0005, "roads", 1),
                ("other_dim", 0.0006, "roads", 1), ("no_vector", 0.0007, "roads", 1), ("far_but_identical", 0.05, "roads", 1), ("other_category", 0.0001, "water_supply", 1),
                ("too_old", 0.0001, "roads", 90))
    d = 384
    repo.save_embedding(ids["subject"], unit(d, 0), "m@1")
    repo.save_embedding(ids["close"], unit(d, 0, 1, 0.1), "m@1")
    repo.save_embedding(ids["orthogonal"], unit(d, 2), "m@1")
    repo.save_embedding(ids["opposite"], [-x for x in unit(d, 0)], "m@1")
    repo.save_embedding(ids["other_model"], unit(d, 0), "other@1")
    repo.save_embedding(ids["other_dim"], unit(768, 0), "m@1")
    for n in ("far_but_identical", "other_category", "too_old"):
        repo.save_embedding(ids[n], unit(d, 0), "m@1")
    name = {v: k for k, v in ids.items()}
    snap, got = search(repo, ids["subject"])
    assert [name[c.id] for c in got] == ["close", "orthogonal", "opposite", "other_model", "other_dim", "no_vector"]      # cosine order first, then the rest nearest-first
    by = {name[c.id]: c for c in got}
    assert all(by[n].embedding is not None for n in ("close", "orthogonal", "opposite")) and all(by[n].embedding is None for n in ("other_model", "other_dim", "no_vector"))


def test_the_sql_uses_the_partial_index_cast_the_dimension_predicate_and_the_gate_in_one_statement(pg, repo):
    ids = cases(("s", 0.0, "roads", 1), ("a", 0.0002, "roads", 1))
    repo.save_embedding(ids["s"], unit(384, 0), "m@1")
    repo.save_embedding(ids["a"], unit(384, 1), "m@1")
    seen: list[str] = []

    def spy(conn, cursor, statement, parameters, context, executemany):
        seen.append(statement)

    event.listen(pg, "before_cursor_execute", spy)
    from backend.db import session as dbs
    event.listen(dbs.engine, "before_cursor_execute", spy)
    try:
        search(repo, ids["s"])
    finally:
        event.remove(dbs.engine, "before_cursor_execute", spy)
        event.remove(pg, "before_cursor_execute", spy)
    [sql] = [s for s in seen if "embedding_vec" in s and "ORDER BY" in s]
    assert "embedding_vec::vector(384) <=> CAST(%(q)s AS vector(384))" in sql                      # the expression of ix_case_embeddings_vec_384
    assert "e.embedding_dim = 384" in sql and "e.embedding_model = %(model)s" in sql and "e.embedding_vec IS NOT NULL" in sql
    assert "ST_DWithin" in sql and "c.category = %(cat)s" in sql and "c.created_at BETWEEN" in sql and "LIMIT %(n)s" in sql      # the deterministic gate is part of the same query


def test_768_dimensional_vectors_use_their_own_cast_and_never_meet_384_ones(pg, repo):
    ids = cases(("s", 0.0, "roads", 1), ("same_dim", 0.0002, "roads", 1), ("other_dim", 0.0003, "roads", 1))
    repo.save_embedding(ids["s"], unit(768, 7), "e5-base")
    repo.save_embedding(ids["same_dim"], unit(768, 7, 8, 0.2), "e5-base")
    repo.save_embedding(ids["other_dim"], unit(384, 7), "e5-base")                                 # same model name, other dimension: not comparable
    _, got = search(repo, ids["s"])
    assert [c.id for c in got] == [ids["same_dim"], ids["other_dim"]] and got[0].embedding is not None and got[1].embedding is None


def test_at_most_50_candidates_are_ranked_in_sql(pg, repo):
    specs = [("s", 0.0, "roads", 1)] + [(f"c{i:02d}", 0.00002 * (i + 1), "roads", 1) for i in range(60)]
    ids = cases(*specs)
    repo.save_embedding(ids["s"], unit(384, 0), "m@1")
    for i in range(60):
        repo.save_embedding(ids[f"c{i:02d}"], unit(384, 0, 1 + i, 0.01 * (i + 1)), "m@1")        # the larger i, the more it differs from the subject
    _, got = search(repo, ids["s"], max_candidates=500)
    assert len(got) == 60                                                                       # 50 ranked by cosine, then the other 10 gated cases nearest-first
    name = {v: k for k, v in ids.items()}
    assert [name[c.id] for c in got[:50]] == [f"c{i:02d}" for i in range(50)]                   # the 50 ranked by cosine: most similar first
    assert len(search(repo, ids["s"], max_candidates=50)[1]) == 50


def test_the_python_path_gives_the_same_order_when_the_extension_is_not_used(pg, repo, monkeypatch):
    ids = cases(("s", 0.0, "roads", 1), ("a", 0.0002, "roads", 1), ("b", 0.0003, "roads", 1), ("c", 0.0004, "roads", 1), ("d", 0.0005, "roads", 1))
    repo.save_embedding(ids["s"], unit(384, 0), "m@1")
    repo.save_embedding(ids["a"], unit(384, 1), "m@1")
    repo.save_embedding(ids["b"], unit(384, 0, 1, 0.3), "m@1")
    repo.save_embedding(ids["c"], unit(384, 0, 2, 0.1), "m@1")
    with_pgvector = [c.id for c in search(repo, ids["s"])[1]]
    monkeypatch.setattr("backend.ai_gateway.vectors.vector_search_available", lambda db: False)
    assert [c.id for c in search(repo, ids["s"])[1]] == with_pgvector == [ids["c"], ids["b"], ids["a"], ids["d"]]
    # and saving without the extension keeps the JSON vector only
    assert repo.save_embedding(ids["d"], unit(384, 4), "m@1")["pgvector"] is False


def test_the_embed_job_writes_everything_on_postgres_and_candidate_search_finds_it(pg, repo, tmp_path):
    from backend.ai_gateway import configure_gateway, get_gateway
    from backend.ai_gateway.sql import build_sql_gateway
    from backend.db import session as dbs
    from backend.services.ai_jobs import run_job
    pytest.importorskip("onnx")
    pytest.importorskip("onnxruntime")
    from backend.ai_gateway.text_model import OnnxEmbedder
    from backend.tests.onnx_artifacts import write_m7_artifact
    ids = cases(("a", 0.0, "roads", 1), ("b", 0.0002, "roads", 1))
    with dbs.SessionLocal() as db:
        db.execute(text("UPDATE civic_cases SET description = 'big pothole near the school' WHERE id = :i"), {"i": ids["a"]})
        db.execute(text("UPDATE civic_cases SET description = 'pothole near the school' WHERE id = :i"), {"i": ids["b"]})
        db.commit()
    configure_gateway(build_sql_gateway())
    try:
        get_gateway().embedder = OnnxEmbedder(write_m7_artifact(tmp_path / "m7", dim=384))
        assert run_job("embed", ids["a"]) == "embed: stored (civic-embed-m7@test-1, 384d, pgvector=True)"
        assert run_job("embed", ids["b"]).startswith("embed: stored")
        with dbs.SessionLocal() as db:
            assert tuple(db.execute(text("SELECT embedding_dim, embedding_model, vector_dims(embedding_vec) FROM case_embeddings WHERE case_id = :i"), {"i": ids["a"]}).one()) == (384, "civic-embed-m7@test-1", 384)
        assert [c.id for c in search(repo, ids["a"])[1]] == [ids["b"]]
    finally:
        configure_gateway(None)
