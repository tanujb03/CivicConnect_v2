import json
from datetime import timedelta

import pytest

from ai.inference.errors import ArtifactError, ProviderUnavailable
from ai.inference.fusion.scoring import FusionWeights
from ai.inference.fusion.service import FusionService
from ai.inference.fusion.similarity import (
    category_signal,
    cosine,
    geospatial_signal,
    haversine_m,
    lexical_similarity,
    temporal_signal,
)
from ai.inference.providers.fake import FakeProvider
from ai.inference.schemas import FusionCase, FusionRequest, W

from .conftest import NOW

LAT, LON = 19.0760, 72.8777


def case(cid, *, d_lat_m=0.0, hours=0.0, cat="roads", sub="pothole", text="big pothole near the school", emb=None):
    return FusionCase(case_id=cid, category=cat, subcategory=sub, latitude=LAT + d_lat_m / 111_195.0, longitude=LON,
                      created_at=NOW - timedelta(hours=hours), text=text, embedding=emb)


CAL = FusionWeights(-3.5, 2.0, 2.5, 0.5, 1.5, status="calibrated_synthetic", semantic_trained_on="lexical", version="t")


def analyze(subject, cands, **kw):
    return FusionService(**kw).analyze(FusionRequest(subject=subject, candidates=cands))


def test_haversine_known_distances():
    assert abs(haversine_m(LAT, LON, LAT + 0.001, LON) - 111.2) < 0.5
    assert haversine_m(LAT, LON, LAT, LON) == 0
    assert abs(haversine_m(0, 0, 0, 1) - 111_195) < 100


def test_signals_are_bounded_and_monotonic():
    assert geospatial_signal(0, 150) == 1 and geospatial_signal(150, 150) == 0 and geospatial_signal(500, 150) == 0
    assert geospatial_signal(30, 150) > geospatial_signal(90, 150)
    assert temporal_signal(0, 30) == 1 and temporal_signal(24 * 30, 30) == 0 and temporal_signal(10, 30) > temporal_signal(100, 30)
    assert category_signal("roads", "pothole", "roads", "pothole") == 1 and category_signal("roads", "pothole", "roads", "x") == 0.5
    assert category_signal("roads", "p", "water_supply", "p") == 0
    assert lexical_similarity("big pothole", "big pothole") > 0.99 and lexical_similarity("abc", "xyz") == 0 and lexical_similarity("", "x") == 0
    assert cosine([1, 0], [1, 0]) == 1 and cosine([1, 0], [0, 1]) == 0 and cosine([1], [1, 2]) == 0 and cosine([1, 0], [-1, 0]) == 0


def test_candidate_gate_excludes_out_of_policy_cases():
    s = FusionService()
    subj = case("S")
    assert s.in_policy(subj, case("near", d_lat_m=20))[0]
    assert not s.in_policy(subj, case("far", d_lat_m=400))[0]
    assert not s.in_policy(subj, case("old", hours=24 * 31))[0]
    assert not s.in_policy(subj, case("othercat", cat="water_supply", sub="pipe_leakage"))[0]
    assert not s.in_policy(subj, case("S"))[0]  # never matches itself


def test_generate_candidates_is_deterministic_and_sorted_by_distance():
    s = FusionService()
    pool = [case("c3", d_lat_m=90), case("c1", d_lat_m=10), case("c2", d_lat_m=50), case("x", d_lat_m=900)]
    assert [c.case_id for c in s.generate_candidates(case("S"), pool)] == ["c1", "c2", "c3"]
    assert s.candidate_query_params() == {**s.policy["candidate_generation"]}


def test_near_identical_report_is_a_possible_duplicate():
    r = analyze(case("S"), [case("C1", d_lat_m=12, hours=3)], weights=CAL)
    m = r.matches[0]
    assert r.recommendation == "POSSIBLE_DUPLICATE" and m.similarity >= 0.8 and m.distance_m < 15
    assert set(m.signals.model_dump()) >= {"semantic", "geospatial", "temporal", "visual"} and m.semantic_source == "lexical"


def test_distant_different_report_is_not_a_match():
    r = analyze(case("S"), [case("C1", d_lat_m=140, hours=500, sub="road_cave_in", text="the street has subsided")], weights=CAL)
    assert r.recommendation == "NO_MATCH" and r.matches == []


def test_score_decreases_with_distance():
    scores = [analyze(case("S"), [case("C", d_lat_m=d)], weights=CAL, policy={**FusionService().policy, "thresholds": {"possible_duplicate": 0.8, "related": 0.0}}).matches[0].similarity
              for d in (5, 40, 90, 140)]
    assert scores == sorted(scores, reverse=True)


def test_matches_sorted_and_capped():
    pool = [case(f"C{i}", d_lat_m=i * 2, hours=i) for i in range(1, 11)]
    r = analyze(case("S"), pool, weights=CAL)
    sims = [m.similarity for m in r.matches]
    assert len(r.matches) <= 5 and sims == sorted(sims, reverse=True)


def test_out_of_policy_candidates_are_ignored_with_a_warning():
    r = analyze(case("S"), [case("far", d_lat_m=900), case("near", d_lat_m=5)], weights=CAL)
    assert [m.case_id for m in r.matches] == ["near"] and any(w.startswith(W.FUSION_CANDIDATE_OUT_OF_POLICY) for w in r.warnings)


def test_no_candidates_is_a_clean_no_match():
    r = analyze(case("S"), [])
    assert r.recommendation == "NO_MATCH" and r.matches == [] and r.ai_metadata.input_refs == ["S"]


def test_uncalibrated_prior_is_always_disclosed():
    r = analyze(case("S"), [case("C", d_lat_m=5)])
    assert any(w.startswith(W.FUSION_UNCALIBRATED_PRIOR) for w in r.warnings)
    r2 = analyze(case("S"), [case("C", d_lat_m=5)], weights=CAL)
    assert not any(w.startswith(W.FUSION_UNCALIBRATED_PRIOR) for w in r2.warnings)


def test_lexical_only_is_disclosed():
    r = analyze(case("S"), [case("C", d_lat_m=5)], weights=CAL)
    assert any(w.startswith(W.FUSION_LEXICAL_ONLY) for w in r.warnings) and r.ai_metadata.fallback_reason == "lexical_semantic_only"


def test_provider_embeddings_are_used_when_available():
    p = FakeProvider()
    r = analyze(case("S"), [case("C", d_lat_m=5, text="a large pothole by the school")], weights=CAL, provider=p)
    assert r.matches[0].semantic_source == "embedding" and r.ai_metadata.source == "provider+rules" and r.ai_metadata.model == "fake-embedding"
    # lexical-fitted weights are NOT applied to embedding scores: the (uncalibrated) embedding weights are used and disclosed
    assert any(w.startswith(W.FUSION_UNCALIBRATED_PRIOR) and "embedding" in w for w in r.warnings)
    assert len([c for c in p.calls if c[0] == "embed"]) == 1  # single batched call, no per-candidate LLM


def test_supplied_embeddings_avoid_provider_calls():
    p = FakeProvider()
    s, c = case("S", emb=[1.0, 0.0]), case("C", d_lat_m=5, emb=[1.0, 0.0])
    r = analyze(s, [c], weights=CAL, provider=p)
    assert r.matches[0].signals.semantic == 1.0 and not p.calls


def test_embedding_dimension_mismatch_falls_back_to_lexical_for_that_pair():
    r = analyze(case("S", emb=[1.0, 0.0]), [case("C", d_lat_m=5, emb=[1.0, 0.0, 0.0])], weights=CAL)
    assert r.matches[0].semantic_source == "lexical"


def test_embedding_failure_degrades_to_lexical():
    p = FakeProvider()
    p.embed = lambda texts: (_ for _ in ()).throw(ProviderUnavailable("down"))  # type: ignore[assignment]
    r = analyze(case("S"), [case("C", d_lat_m=5)], weights=CAL, provider=p)
    assert r.matches[0].semantic_source == "lexical" and any(w.startswith(W.PROVIDER_UNAVAILABLE) for w in r.warnings)


def test_results_are_deterministic():
    a = analyze(case("S"), [case("C1", d_lat_m=12), case("C2", d_lat_m=30)], weights=CAL)
    b = analyze(case("S"), [case("C1", d_lat_m=12), case("C2", d_lat_m=30)], weights=CAL)
    assert [m.model_dump() for m in a.matches] == [m.model_dump() for m in b.matches]


def test_weights_load_and_validate(tmp_path):
    f = tmp_path / "fusion_weights.json"
    f.write_text(json.dumps({"schema": "civic-fusion-weights/1", "bias": -1, "semantic": 1, "geospatial": 2, "temporal": 0.5, "category": 1,
                             "status": "calibrated_synthetic", "version": "v"}))
    w = FusionWeights.load(tmp_path)
    assert w.status == "calibrated_synthetic" and 0 < w.score(1, 1, 1, 1) < 1 and w.score(0, 0, 0, 0) < w.score(1, 1, 1, 1)
    f.write_text(json.dumps({"schema": "wrong"}))
    with pytest.raises(ArtifactError):
        FusionWeights.load(f)
    with pytest.raises(ArtifactError):
        FusionWeights.load(tmp_path / "missing.json")


def test_committed_calibrated_weights_load_if_present():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "artifacts" / "fusion_calibrator"
    dirs = sorted((d for d in root.glob("*/") if (d / "fusion_weights.json").exists()),
                  key=lambda d: (d / "fusion_weights.json").stat().st_mtime) if root.exists() else []
    if not dirs:
        pytest.skip("no fusion calibrator artifact generated yet")
    w = FusionWeights.load(dirs[-1])
    assert w.status == "calibrated_synthetic" and w.geospatial > 0
    # every signal is monotone: no weight may be negative (higher similarity must never lower the score)
    assert min(w.semantic, w.geospatial, w.temporal, w.category) >= 0


def test_weights_are_selected_per_semantic_mode():
    lex = FusionWeights(-3.5, 0.0, 2.5, 0.5, 1.5, status="calibrated_synthetic", semantic_trained_on="lexical", version="L")
    emb = FusionWeights(-3.5, 4.0, 2.5, 0.5, 1.5, status="calibrated_synthetic", semantic_trained_on="embedding", version="E")
    s, c = case("S", emb=[1.0, 0.0]), case("C", d_lat_m=60, emb=[1.0, 0.0])
    lexical = FusionService(weights=lex, embedding_weights=emb).analyze(FusionRequest(subject=case("S"), candidates=[case("C", d_lat_m=60)]))
    embedded = FusionService(weights=lex, embedding_weights=emb).analyze(FusionRequest(subject=s, candidates=[c]))
    assert embedded.matches[0].semantic_source == "embedding" and embedded.ai_metadata.model_version == "E"
    assert embedded.matches[0].similarity > lexical.matches[0].similarity
    assert not any(w.startswith(W.FUSION_UNCALIBRATED_PRIOR) for w in embedded.warnings)
