"""Embeddings in the civic:ai_jobs worker (local M7, else the provider's embedder, else skipped with a warning) and AI-2 candidate search on the portable path
(SQLite, or PostgreSQL without pgvector): deterministic gate first, then Python cosine over the gated set (cap 200), comparing only vectors of the same model and dimension.
The pgvector path runs against PostgreSQL in test_postgres_vector_search.py."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from ai.inference.providers.fake import FakeProvider
from backend.ai_gateway import vectors
from backend.models import AIAnalysis, CaseEmbedding, CaseEvent, CivicCase
from backend.models.types import new_id
from backend.tests.ai_helpers import SpeechProvider, install
from backend.tests.helpers import create_case

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)


def rows(e, model, **where):
    with e.session_factory() as db:
        return db.query(model).filter_by(**where).all()


def local_m7(tmp_path, dim=384):
    pytest.importorskip("onnx")
    pytest.importorskip("onnxruntime")
    pytest.importorskip("tokenizers")
    from backend.ai_gateway.text_model import OnnxEmbedder
    from backend.tests.onnx_artifacts import write_m7_artifact
    return OnnxEmbedder(write_m7_artifact(tmp_path / "m7", dim=dim))


class BrokenEmbedder:
    tag = "broken@1"

    def embed(self, texts):
        raise RuntimeError("onnx session died")


# ---- the embed job -----------------------------------------------------------------------------------------------------------------------------------------------
def test_embed_job_with_the_local_m7_stores_the_json_vector_and_the_dimension_columns(staffed, tmp_path):
    from backend.services.ai_jobs import run_job
    e = staffed
    install(embedder=local_m7(tmp_path))
    case = create_case(e, "alice", description="big pothole near the school")
    out = run_job("embed", case["id"])
    assert out == "embed: stored (civic-embed-m7@test-1, 384d, pgvector=False)"                  # SQLite: no pgvector, the JSON vector is the store
    [emb] = rows(e, CaseEmbedding, case_id=case["id"])
    assert len(emb.vector) == 384 and emb.embedding_dim == 384 and emb.embedding_model == emb.model == "civic-embed-m7@test-1"
    assert sum(x * x for x in emb.vector) == pytest.approx(1.0, abs=1e-3)
    [a] = rows(e, AIAnalysis, case_id=case["id"], task_type="embedding")
    assert a.source == "local_m7" and a.model == "civic-embed-m7@test-1" and a.degraded is False and a.result_json["dim"] == 384 and a.result_json["pgvector"] is False
    [ev] = [x for x in rows(e, CaseEvent, case_id=case["id"]) if x.event_type == "CASE_EMBEDDED"]
    assert ev.visibility == "INTERNAL" and ev.event_metadata["dim"] == 384
    run_job("embed", case["id"])                                                                 # re-running replaces, never duplicates
    assert len(rows(e, CaseEmbedding, case_id=case["id"])) == 1


def test_embed_job_falls_back_to_the_provider_when_there_is_no_local_model(staffed):
    from backend.services.ai_jobs import run_job
    e = staffed
    p = FakeProvider(dim=64)
    install(p)
    case = create_case(e, "alice")
    assert run_job("embed", case["id"]).startswith("embed: stored (provider:fake-embedding, 64d")
    [emb] = rows(e, CaseEmbedding, case_id=case["id"])
    assert emb.embedding_model == "provider:fake-embedding" and emb.embedding_dim == 64 and len(emb.vector) == 64
    assert [a.source for a in rows(e, AIAnalysis, case_id=case["id"], task_type="embedding")] == ["provider"]
    assert [k for k, *_ in p.calls].count("embed") == 1


def test_embed_job_skips_with_a_visible_warning_when_nothing_can_embed(staffed):
    from backend.services.ai_jobs import run_job
    e = staffed
    install(None)
    case = create_case(e, "alice")
    assert run_job("embed", case["id"]) == "embed: skipped"
    assert rows(e, CaseEmbedding, case_id=case["id"]) == []
    [a] = rows(e, AIAnalysis, case_id=case["id"], task_type="embedding")
    assert a.degraded is True and a.source == "none" and any(w.startswith("NO_EMBEDDER") for w in a.result_json["warnings"])
    [ev] = [x for x in rows(e, CaseEvent, case_id=case["id"]) if x.event_type == "EMBEDDING_SKIPPED"]
    assert ev.event_metadata["warnings"]


def test_a_broken_local_model_falls_back_to_the_provider_with_a_warning_and_never_fails(staffed):
    from backend.services.ai_jobs import run_job
    e = staffed
    install(FakeProvider(dim=32), embedder=BrokenEmbedder())
    case = create_case(e, "alice")
    assert run_job("embed", case["id"]).startswith("embed: stored (provider:fake-embedding")
    [a] = rows(e, AIAnalysis, case_id=case["id"], task_type="embedding")
    assert a.degraded is True and any(w.startswith("LOCAL_EMBEDDER_FAILED") for w in a.result_json["warnings"])
    install(None, embedder=BrokenEmbedder())
    other = create_case(e, "alice", client_case_id="c2")
    assert run_job("embed", other["id"]) == "embed: skipped"
    [b] = rows(e, AIAnalysis, case_id=other["id"], task_type="embedding")
    assert {w.split(":")[0] for w in b.result_json["warnings"]} == {"LOCAL_EMBEDDER_FAILED", "NO_EMBEDDER"}


def test_a_failing_embedding_provider_skips_with_a_warning(staffed):
    from backend.services.ai_jobs import run_job

    class Down(FakeProvider):
        def embed(self, texts):
            raise ConnectionError("no route")

    e = staffed
    install(Down())
    case = create_case(e, "alice")
    assert run_job("embed", case["id"]) == "embed: skipped"
    assert any(w.startswith("PROVIDER_UNAVAILABLE") for w in rows(e, AIAnalysis, case_id=case["id"], task_type="embedding")[0].result_json["warnings"])


def test_a_provider_that_only_does_speech_has_no_embedding_model_and_is_skipped(staffed):
    from backend.services.ai_jobs import run_job
    e = staffed
    install(SpeechProvider(models={"embedding": ""}))                                             # model_for("embedding") is falsy: not configured
    case = create_case(e, "alice")
    assert run_job("embed", case["id"]) == "embed: skipped"


def test_the_embedding_is_computed_from_the_text_including_the_transcript(staffed, tmp_path):
    from backend.services.ai_jobs import run_job
    from backend.tests.helpers import WAV, upload
    e = staffed
    install(SpeechProvider(transcript="garbage near the market"), embedder=local_m7(tmp_path))
    ev = upload(e, "alice", data=WAV, mime="audio/wav", name="v.wav")["id"]
    case = create_case(e, "alice", description="water leak", evidence_ids=[ev])
    run_job("embed", case["id"])
    before = rows(e, CaseEmbedding, case_id=case["id"])[0].vector
    run_job("transcribe", case["id"])
    run_job("embed", case["id"])
    after = rows(e, CaseEmbedding, case_id=case["id"])[0].vector
    assert vectors.cosine(before, after) < 0.999                                                  # the spoken words changed the embedding


# ---- candidate search: portable path -----------------------------------------------------------------------------------------------------------------------------
def make_case(db, lat, lon, *, category="roads", age_days=1.0, number=None):
    c = CivicCase(id=new_id(), case_number=number or f"T-{new_id()[:8]}", title="t", description="t", category=category, subcategory="pothole", latitude=lat, longitude=lon,
                  created_at=NOW - timedelta(days=age_days), updated_at=NOW, status="NEEDS_REVIEW", priority="NORMAL")
    db.add(c)
    db.flush()
    return c


def put_embedding(repo, cid, vec, model="m@1"):
    repo.save_embedding(cid, vec, model)


@pytest.fixture
def repo(staffed):
    from backend.ai_gateway.sql import SqlCaseRepository
    return SqlCaseRepository()


def search(repo, subject_id, **kw):
    snap = repo.get_case(subject_id)
    args = dict(radius_m=300.0, time_window_days=30, max_candidates=50, same_category=True)
    return snap, repo.fusion_candidates(snap, **{**args, **kw})


def test_python_cosine_ranks_the_gated_set_and_only_compares_same_model_and_dimension(staffed, repo):
    e = staffed
    lat, lon = e.where["latitude"], e.where["longitude"]
    with e.session_factory() as db:
        ids = {n: make_case(db, lat + d, lon, category=cat, age_days=age).id for n, d, cat, age in [
            ("subject", 0.0, "roads", 1), ("near_opposite", 0.0002, "roads", 1), ("near_same", 0.0003, "roads", 1), ("near_other_model", 0.0004, "roads", 1),
            ("near_other_dim", 0.0005, "roads", 1), ("near_no_vector", 0.0006, "roads", 1), ("far", 0.05, "roads", 1), ("other_category", 0.0001, "water_supply", 1),
            ("too_old", 0.0001, "roads", 90)]}
        db.commit()
    put_embedding(repo, ids["subject"], [1.0, 0.0, 0.0, 0.0])
    put_embedding(repo, ids["near_opposite"], [0.0, 1.0, 0.0, 0.0])
    put_embedding(repo, ids["near_same"], [0.9, 0.1, 0.0, 0.0])
    put_embedding(repo, ids["near_other_model"], [1.0, 0.0, 0.0, 0.0], model="other@1")
    put_embedding(repo, ids["near_other_dim"], [1.0, 0.0, 0.0], model="m@1")
    for n in ("far", "other_category", "too_old"):
        put_embedding(repo, ids[n], [1.0, 0.0, 0.0, 0.0])
    snap, got = search(repo, ids["subject"])
    order = [c.id for c in got]
    name = {v: k for k, v in ids.items()}
    assert [name[i] for i in order] == ["near_same", "near_opposite", "near_other_model", "near_other_dim", "near_no_vector"]       # ranked first, then the rest nearest-first
    assert snap.embedding_model == "m@1" and len(snap.embedding) == 4
    by = {name[c.id]: c for c in got}
    assert by["near_same"].embedding is not None and by["near_opposite"].embedding is not None                                    # comparable vectors are kept
    assert all(by[n].embedding is None and by[n].embedding_model is None for n in ("near_other_model", "near_other_dim", "near_no_vector"))   # incomparable ones are not offered


def test_the_gate_is_applied_before_similarity_category_radius_and_window(staffed, repo):
    e = staffed
    lat, lon = e.where["latitude"], e.where["longitude"]
    with e.session_factory() as db:
        s = make_case(db, lat, lon).id
        same_cat = make_case(db, lat + 0.0001, lon).id                                       # ~11 m away, 1 day old
        other_cat = make_case(db, lat + 0.0001, lon, category="water_supply").id
        older = make_case(db, lat + 0.0001, lon, age_days=11).id                             # 10 days before the subject
        db.commit()
    for cid in (s, same_cat, other_cat, older):
        put_embedding(repo, cid, [1.0, 0.0])                                                  # identical vectors: only the gate can exclude
    assert {c.id for c in search(repo, s)[1]} == {same_cat, older}
    assert {c.id for c in search(repo, s, same_category=False)[1]} == {same_cat, other_cat, older}
    assert search(repo, s, radius_m=5.0)[1] == []                                            # nobody within 5 m
    assert {c.id for c in search(repo, s, time_window_days=5)[1]} == {same_cat}                # the 10-day-old case is outside a 5-day window


def test_subject_without_a_vector_gets_the_gated_set_nearest_first(staffed, repo):
    e = staffed
    lat, lon = e.where["latitude"], e.where["longitude"]
    with e.session_factory() as db:
        s = make_case(db, lat, lon).id
        far, near = make_case(db, lat + 0.0008, lon).id, make_case(db, lat + 0.0002, lon).id
        db.commit()
    put_embedding(repo, near, [1.0, 0.0])
    snap, got = search(repo, s)
    assert snap.embedding is None and [c.id for c in got] == [near, far]                       # no ranking possible: geographic order, vectors untouched
    assert got[0].embedding == [1.0, 0.0]


def test_legacy_rows_without_dimension_and_model_columns_still_compare(staffed, repo):
    e = staffed
    lat, lon = e.where["latitude"], e.where["longitude"]
    with e.session_factory() as db:
        s, a, b = (make_case(db, lat + d, lon).id for d in (0.0, 0.0002, 0.0003))
        db.add_all([CaseEmbedding(case_id=s, model="old@1", vector=[1.0, 0.0]), CaseEmbedding(case_id=a, model="old@1", vector=[0.0, 1.0]),
                    CaseEmbedding(case_id=b, model="old@1", vector=[0.95, 0.05])])
        db.commit()                                                                              # embedding_dim / embedding_model stay NULL, as before migration 0003
    assert [c.id for c in search(repo, s)[1]] == [b, a]


def test_the_portable_path_compares_at_most_200_gated_cases_and_returns_at_most_max_candidates(staffed, repo):
    e = staffed
    lat, lon = e.where["latitude"], e.where["longitude"]
    with e.session_factory() as db:
        s = make_case(db, lat, lon).id
        for i in range(230):
            make_case(db, lat + 0.00001 * (i + 1), lon)
        db.commit()
    _, got = search(repo, s, radius_m=5000.0, max_candidates=500)
    assert len(got) == repo.PORTABLE_CAP == 200
    assert len(search(repo, s, radius_m=5000.0, max_candidates=50)[1]) == 50


def test_ranked_candidates_reach_the_fusion_ai_and_the_near_duplicate_wins(staffed, tmp_path):
    from backend.services.ai_jobs import run_job
    e = staffed
    install(embedder=local_m7(tmp_path))
    first = create_case(e, "alice", description="big pothole near the school")
    dup = create_case(e, "bob", description="pothole near the school")
    unrelated = create_case(e, "bob", description="garbage water leak street light")
    for c in (first, dup, unrelated):
        run_job("embed", c["id"])
    res = e.client.post(f"/api/v1/cases/{dup['id']}/fusion/analyze", headers=e.headers("roads_op")).json()
    assert res["matches"][0]["case_id"] == first["id"] and "semantic" in res["matches"][0]["signals"]["signals_available"]
    assert res["matches"][0]["semantic_source"]
