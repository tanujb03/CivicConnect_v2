"""Duplicate threshold calibration (backend/scripts/calibrate_duplicates.py) on a tiny synthetic city with deterministic fake vectors: the deterministic gate filters the pairs,
the threshold rule on known score distributions, the 90% coverage refusal, the outputs. SQLite only; no provider, no network."""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone

import pytest

from ai.inference.config import load_fusion_policy
from backend.models import CaseEmbedding, CivicCase
from backend.scripts import calibrate_duplicates as cal

POLICY = load_fusion_policy()
CG = POLICY["candidate_generation"]            # same category, 150 m, 30 days
LAT0, LON0, M = 19.0, 72.9, 1 / 111_320        # one metre of latitude in degrees


def unit(angle: float) -> list[float]:
    return [math.cos(angle), math.sin(angle), 0.0, 0.0]


def case(cid: str, y_m: float, *, category="roads", status="NEEDS_REVIEW", day=10) -> dict:
    return {"id": cid, "category": category, "subcategory": "pothole", "status": status, "location": {"latitude": LAT0 + y_m * M, "longitude": LON0},
            "created_at": f"2026-03-{day:02d}T10:00:00Z"}


def tiny_city() -> tuple[dict, dict[str, tuple[str, list[float]]]]:
    """24 cases: 5 planted duplicate pairs (cosines .999 .995 .989 .980 .955), 1 planted pair OUTSIDE the gate (500 m), 3 near-distinct pairs inside the gate (cosines .825 .697 .540),
    1 near-distinct pair outside it (300 m), 1 unlabelled pair inside the gate (.267), a REJECTED case and a case of another category next to planted ones."""
    cases, vec = [], {}
    dup_deltas, near_deltas = [0.05, 0.1, 0.15, 0.2, 0.3], [0.6, 0.8, 1.0]
    gt: dict = {"possible_duplicate_pairs": [], "near_distinct_pairs": [], "duplicate_groups_merged": [{"case_id": "pa0", "signal_ids": ["s1", "s2", "s3"]}, {"case_id": "x", "signal_ids": ["s4", "s5"]}]}

    def pair(prefix: str, i: int, y: float, gap: float, delta: float, label: list) -> None:
        a, b = f"{prefix}a{i}", f"{prefix}b{i}"
        cases.extend([case(a, y), case(b, y + gap)])
        base = 0.37 * (len(cases) + 1)
        vec[a], vec[b] = ("fake@1", unit(base)), ("fake@1", unit(base + delta))
        label.append({"case_a": a, "case_b": b, "distance_m": gap})

    for i, d in enumerate(dup_deltas):
        pair("p", i, i * 2000, 20, d, gt["possible_duplicate_pairs"])
    pair("po", 0, 20000, 500, 0.05, gt["possible_duplicate_pairs"])                       # planted duplicate that the gate (150 m) rejects
    for i, d in enumerate(near_deltas):
        pair("n", i, 30000 + i * 2000, 100, d, gt["near_distinct_pairs"])
    pair("no", 0, 40000, 300, 0.9, gt["near_distinct_pairs"])                             # near-distinct but outside the radius
    pair("og", 0, 50000, 50, 1.3, [])                                                      # unlabelled, inside the gate
    cases.append(case("rejected", 50010, status="REJECTED"))
    cases.append(case("other_cat", 5, category="water"))
    vec["rejected"], vec["other_cat"] = ("fake@1", unit(0.123)), ("fake@1", unit(2.0))
    return {"cases": cases, "ground_truth": gt}, vec


# ---- the gate filters the pairs -----------------------------------------------------------------------------------------------------------------------------------
def test_the_gate_applies_category_radius_and_time_window_from_the_policy():
    a = cal.city_cases({"cases": [case("a", 0), case("near", 100), case("far", 400), case("water", 10, category="water"), case("late", 10, day=28), case("later", 10, day=11)]})
    assert cal.gate(a["a"], a["near"], CG)[0] and cal.gate(a["a"], a["later"], CG)[0]
    assert not cal.gate(a["a"], a["far"], CG)[0] and not cal.gate(a["a"], a["water"], CG)[0]
    ok, d, age_h = cal.gate(a["a"], a["near"], CG)
    assert d == pytest.approx(100, abs=1) and age_h == 0
    late = cal.gate(a["a"], a["late"], {**CG, "time_window_days": 7})
    assert late[0] is False and late[2] == pytest.approx(18 * 24)
    assert cal.gate(a["a"], a["water"], {**CG, "same_category_required": False})[0] is True


def test_pairs_are_classified_by_the_gate_and_the_rest_of_the_gate_pairs_are_hard_negatives():
    city, _ = tiny_city()
    pr = cal.build_pairs(city, CG, samples=40, seed=7)
    assert len(pr["positives"]) == 5 and pr["positives_planted"] == 6                      # po0 is rejected by the gate (500 m)
    assert len(pr["near_distinct"]) == 3 and pr["near_distinct_planted"] == 4
    assert pr["other_gated"] == [cal.key("oga0", "ogb0")]                                  # the REJECTED and the other-category case never form a pair
    assert pr["merged_signal_pairs"] == 3                                                  # (3 - 1) + (2 - 1): reports inside merged cases, not scorable by case embeddings
    labelled = {tuple(p) for p in pr["positives"]} | {tuple(p) for p in pr["near_distinct"]} | {tuple(p) for p in pr["other_gated"]}
    cases = pr["cases"]
    assert pr["out_of_gate"] and all(not cal.gate(cases[a], cases[b], CG)[0] and (a, b) not in labelled for a, b in pr["out_of_gate"])
    assert all("rejected" not in p for p in pr["out_of_gate"] + pr["other_gated"])


def test_the_out_of_gate_sample_is_reproducible_for_a_seed():
    city, _ = tiny_city()
    a, b, c = (cal.build_pairs(city, CG, samples=30, seed=s)["out_of_gate"] for s in (7, 7, 8))
    assert a == b and a != c and len(a) == 30


# ---- the threshold rule --------------------------------------------------------------------------------------------------------------------------------------------------
POS = [0.99, 0.97, 0.96, 0.95, 0.94, 0.93, 0.90, 0.82, 0.70]
NEG = [0.91, 0.86, 0.80, 0.75, 0.60, 0.50]


def test_sweep_counts_precision_recall_and_f1_per_threshold():
    rows = {r["threshold"]: r for r in cal.sweep(POS, NEG, near=[0.91])}
    assert list(rows)[0] == 0.50 and list(rows)[-1] == 0.98 and len(rows) == 25
    r = rows[0.92]
    assert (r["tp"], r["fp"], r["fn"], r["precision"]) == (6, 0, 3, 1.0) and r["recall"] == pytest.approx(6 / 9) and r["f1"] == pytest.approx(0.8)
    r = rows[0.90]
    assert (r["tp"], r["fp"], r["fn"]) == (7, 1, 2) and r["precision"] == pytest.approx(7 / 8) and r["precision_vs_near_distinct"] == pytest.approx(7 / 8)
    assert rows[0.98]["tp"] == 1 and rows[0.98]["precision"] == 1.0
    assert cal.sweep([0.5], [0.4])[-1]["precision"] is None                                 # nothing predicted: precision undefined


def test_duplicate_is_the_lowest_threshold_with_precision_090_and_related_the_lowest_with_075():
    chosen = cal.choose_thresholds(cal.sweep(POS, NEG))
    assert chosen["duplicate_threshold"]["value"] == 0.92 and chosen["related_threshold"]["value"] == 0.82
    assert chosen["duplicate_threshold"]["precision"] == 1.0 and chosen["duplicate_threshold"]["tp"] == 6 and "precision >= 0.90 with at least 5 true positives" in chosen["duplicate_threshold"]["rule"]
    assert chosen["related_threshold"]["precision"] == pytest.approx(0.8) and chosen["warnings"] == [] and chosen["notes"] == []


def test_the_duplicate_threshold_needs_five_true_positives_otherwise_the_f1_fallback_says_so():
    chosen = cal.choose_thresholds(cal.sweep([0.99, 0.98, 0.97, 0.96], [0.5]))           # precision 1.0 from 0.52 up, but only 4 true positives
    d = chosen["duplicate_threshold"]
    assert "F1-maximising" in d["rule"] and any("at least 5 true positives" in w for w in chosen["warnings"])
    assert any("only 4 true positives (< 5): too little support" in n for n in chosen["notes"])
    assert chosen["related_threshold"]["rule"] == "lowest threshold with precision >= 0.75"        # the related rule has no support requirement
    five = cal.choose_thresholds(cal.sweep([0.99, 0.98, 0.97, 0.96, 0.95], [0.5]))
    assert five["duplicate_threshold"]["value"] == 0.52 and five["duplicate_threshold"]["tp"] == 5 and five["warnings"] == []


def test_positives_without_a_vector_count_as_false_negatives_in_every_recall():
    rows = cal.sweep([0.9, 0.8], [0.4], missing_pos=2)
    r = {x["threshold"]: x for x in rows}
    assert (r[0.50]["tp"], r[0.50]["fn"], r[0.50]["recall"]) == (2, 2, 0.5) and r[0.50]["precision"] == 1.0
    assert r[0.82]["fn"] == 3 and r[0.82]["recall"] == pytest.approx(0.25)


def test_without_a_threshold_that_reaches_the_precision_the_f1_maximum_is_chosen_with_a_warning():
    pos, neg = [0.6, 0.7], [0.72] * 10 + [0.5] * 5
    chosen = cal.choose_thresholds(cal.sweep(pos, neg))
    assert chosen["duplicate_threshold"]["value"] == 0.60 and chosen["related_threshold"]["value"] == 0.60         # F1 ties: the higher threshold
    assert "F1-maximising" in chosen["duplicate_threshold"]["rule"] and len(chosen["warnings"]) == 2 and all(w.startswith("WARNING") for w in chosen["warnings"])


def test_related_never_exceeds_duplicate():
    rows = cal.sweep([0.9, 0.8], [0.85, 0.6])                                               # precision .90 first reached high up, .75 reached lower
    chosen = cal.choose_thresholds(rows)
    assert chosen["related_threshold"]["value"] <= chosen["duplicate_threshold"]["value"]


def test_distribution_statistics():
    s = cal.dist_stats([0.1, 0.2, 0.3, 0.4, 0.5])
    assert (s["n"], s["min"], s["max"], s["median"]) == (5, 0.1, 0.5, pytest.approx(0.3)) and s["p10"] == pytest.approx(0.14) and s["p90"] == pytest.approx(0.46)
    assert cal.dist_stats([])["n"] == 0 and cal.dist_stats([0.7])["median"] == 0.7


def test_the_policy_comparison_says_whether_the_fused_thresholds_would_change():
    rows = cal.sweep(POS, NEG)
    chosen = cal.choose_thresholds(rows)
    v = cal.compare_with_policy(rows, chosen, {"possible_duplicate": 0.92, "related": 0.50})
    assert v["duplicate"]["would_change"] is False and v["duplicate"]["difference"] == 0.0 and v["related"]["would_change"] is True and v["related"]["difference"] == 0.32


# ---- the whole analysis ----------------------------------------------------------------------------------------------------------------------------------------------------
def test_calibrate_on_the_tiny_city_with_fake_embeddings():
    city, vec = tiny_city()
    r = cal.calibrate(city, vec, POLICY, samples=40)
    c = r["counts"]
    assert c["positives_in_gate"] == 5 and c["positives_out_of_gate"] == 1 and c["near_distinct_in_gate"] == 3 and c["other_gated"] == 1 and c["coverage"] == 1.0
    assert c["pairs_scored"]["positives"] == 5 and c["model"] == "fake@1" and c["dimension"] == 4 and c["merged_signal_pairs_not_evaluable"] == 3
    d = r["cosine"]["distribution"]
    assert d["positives"]["min"] == pytest.approx(math.cos(0.3)) and d["positives"]["max"] == pytest.approx(math.cos(0.05))
    assert d["near_distinct"]["n"] == 3 and d["near_distinct"]["max"] == pytest.approx(math.cos(0.6)) and d["other_gated"]["max"] == pytest.approx(math.cos(1.3))
    ch = r["cosine"]["chosen"]
    assert ch["duplicate_threshold"]["value"] == 0.84 and ch["related_threshold"]["value"] == 0.70 and ch["duplicate_threshold"]["recall"] == 1.0
    assert any(n.startswith("CAUTION: only 5 positive pairs") and "no real-world claim" in n for n in r["notes"])        # fewer than 30 positives: loud
    assert set(r["fused"]["versus_policy"]) == {"duplicate", "related"} and r["fused"]["weights_status"] == POLICY["prior_weights"]["status"]
    assert r["policy_thresholds"] == POLICY["thresholds"] and r["gate"]["radius_m"] == 150
    json.dumps(r)                                                                             # JSON-able as is


def test_no_caution_with_thirty_positives():
    cases, gt, vec = [], {"possible_duplicate_pairs": [], "near_distinct_pairs": [], "duplicate_groups_merged": []}, {}
    for i in range(30):
        a, b = f"a{i}", f"b{i}"
        cases += [case(a, i * 2000), case(b, i * 2000 + 10)]
        vec[a], vec[b] = ("m", unit(0.5 * i)), ("m", unit(0.5 * i + 0.1))
        gt["possible_duplicate_pairs"].append({"case_a": a, "case_b": b})
    cases += [case("n1", 100000), case("n2", 100050)]
    vec["n1"], vec["n2"] = ("m", unit(0.2)), ("m", unit(1.8))
    gt["near_distinct_pairs"].append({"case_a": "n1", "case_b": "n2"})
    r = cal.calibrate({"cases": cases, "ground_truth": gt}, vec, POLICY, samples=20)
    assert r["notes"] == [] and r["counts"]["pairs_scored"]["positives"] == 30


def test_it_refuses_to_choose_thresholds_below_90_percent_embedded_cases():
    city, vec = tiny_city()
    pairs = cal.build_pairs(city, CG, 40, 7)
    involved = sorted({i for k in ("positives", "near_distinct", "other_gated", "out_of_gate") for p in pairs[k] for i in p})
    keep = {i: v for i, v in vec.items() if i not in involved[: len(involved) // 5 + 1]}          # more than 10% of the involved cases lost their embedding
    with pytest.raises(cal.CoverageError, match="have an embedding"):
        cal.calibrate(city, keep, POLICY, pairs=pairs)
    nine = {i: v for i, v in vec.items() if i not in involved[: len(involved) // 10]}              # at most 10% missing: allowed, those pairs are dropped and counted
    r = cal.calibrate(city, nine, POLICY, pairs=pairs)
    assert r["counts"]["coverage"] >= 0.9 and sum(r["counts"]["pairs_dropped_no_comparable_vector"].values()) > 0
    with pytest.raises(cal.CoverageError):
        cal.calibrate(city, {}, POLICY, pairs=pairs)


def test_vectors_of_another_model_or_dimension_are_not_compared():
    city, vec = tiny_city()
    vec = {**vec, "pa0": ("other-model", unit(1.0))}                         # 1 of the 10 cases of the planted pairs: 90% are still comparable
    r = cal.calibrate(city, vec, POLICY, samples=40)
    assert r["counts"]["pairs_scored"]["positives"] == 4 and r["counts"]["pairs_dropped_no_comparable_vector"]["positives"] == 1
    assert r["counts"]["models_seen"] == ["fake@1", "other-model"] and r["counts"]["positives_counted_as_false_negatives"] == 1
    top = r["cosine"]["sweep"][0]
    assert top["fn"] == 1 and top["recall"] == pytest.approx(4 / 5)                  # the dropped planted pair is a false negative, not forgotten
    assert any("count as FALSE NEGATIVES" in n for n in r["notes"])
    vec["pb1"] = ("fake@1", [1.0, 0.0, 0.0])                                         # a second one with another dimension: 80% of the positives' cases
    with pytest.raises(cal.CoverageError, match="planted duplicate pairs"):
        cal.calibrate(city, vec, POLICY, samples=40)


def test_the_coverage_refusal_also_applies_to_the_positive_class_alone():
    city, vec = tiny_city()
    pairs = cal.build_pairs(city, CG, 40, 7)
    cut = {"pa0", "pb3"}                                                              # 2 of the 10 positive cases (80%), but only 2 of ~24 involved cases (> 90% overall)
    r_ok = cal.calibrate(city, {i: v for i, v in vec.items() if i not in {"pa0"}}, POLICY, pairs=pairs)
    assert r_ok["counts"]["positives_coverage"] == 0.9
    with pytest.raises(cal.CoverageError, match="planted duplicate pairs"):
        cal.calibrate(city, {i: v for i, v in vec.items() if i not in cut}, POLICY, pairs=pairs)


def test_without_any_positive_pair_in_the_gate_it_refuses():
    city, vec = tiny_city()
    city["ground_truth"]["possible_duplicate_pairs"] = []
    with pytest.raises(cal.CoverageError):
        cal.calibrate(city, vec, POLICY, samples=40)


def test_the_markdown_report_has_every_section_and_the_numbers():
    city, vec = tiny_city()
    md = cal.render_markdown(cal.calibrate(city, vec, POLICY, samples=40))
    for part in ("# Duplicate threshold calibration", "SYNTHETIC demo data: no real-world claim", "## Cosine similarity by class", "random pairs OUT of the gate (baseline)",
                 "## Cosine threshold sweep", "| 0.84 |", "`duplicate_threshold` = **0.84**", "`related_threshold` = **0.70**", "## Against the policy file (fused score)",
                 "The policy file was not edited", "CAUTION: only 5 positive pairs", "Not evaluable at case level: 3"):
        assert part in md, part


# ---- database and command line ----------------------------------------------------------------------------------------------------------------------------------------
def put_city_in_db(env, city, vec, skip=()):
    with env.session_factory() as db:
        for c in city["cases"]:
            db.add(CivicCase(id=c["id"], case_number=f"T-{c['id']}", title="t", description="t", category=c["category"], subcategory="pothole", latitude=c["location"]["latitude"],
                             longitude=c["location"]["longitude"], created_at=datetime(2026, 3, 10, 10, tzinfo=timezone.utc), updated_at=datetime(2026, 3, 10, tzinfo=timezone.utc),
                             status=c["status"], priority="NORMAL"))
        db.flush()
        for cid, (model, v) in vec.items():
            if cid not in skip:
                db.add(CaseEmbedding(case_id=cid, model=model, vector=v, embedding_dim=len(v), embedding_model=model))
        db.commit()


def test_load_vectors_reads_the_json_vectors_of_the_requested_cases(env):
    city, vec = tiny_city()
    put_city_in_db(env, city, vec, skip={"pa0"})
    got = cal.load_vectors(["pa0", "pb0", "p-unknown", "n_x"] + [f"pb{i}" for i in range(1, 4)])
    assert set(got) == {"pb0", "pb1", "pb2", "pb3"} and got["pb0"] == ("fake@1", vec["pb0"][1])
    assert cal.load_vectors([]) == {}


def test_main_writes_the_markdown_and_json_reports(env, tmp_path, monkeypatch, capsys):
    city, vec = tiny_city()
    put_city_in_db(env, city, vec)
    monkeypatch.setattr(cal, "load_city", lambda path: city)
    out, js = tmp_path / "docs" / "DUPLICATE_CALIBRATION.md", tmp_path / "calib.json"
    assert cal.main(["--out", str(out), "--json-out", str(js), "--samples", "40"]) == 0
    text = capsys.readouterr().out
    assert "no real-world claim" in text and "duplicate_threshold 0.84" in text and "related_threshold 0.70" in text
    assert out.read_text(encoding="utf-8").startswith("# Duplicate threshold calibration")
    data = json.loads(js.read_text(encoding="utf-8"))
    assert data["cosine"]["chosen"]["duplicate_threshold"]["value"] == 0.84 and data["seed"] == 7


def test_main_refuses_and_writes_nothing_when_too_few_cases_are_embedded(env, tmp_path, monkeypatch, capsys):
    city, vec = tiny_city()
    put_city_in_db(env, city, vec, skip={f"{p}{x}{i}" for p in ("p", "n") for x in "ab" for i in range(3)})
    monkeypatch.setattr(cal, "load_city", lambda path: city)
    out = tmp_path / "report.md"
    assert cal.main(["--out", str(out), "--samples", "40"]) == 2
    assert "REFUSED" in capsys.readouterr().err and not out.exists()
