"""The seeded SYNTHETIC demo city (design §58): determinism, §58 minimums, integrity, labelling, ground truth, evaluation plumbing."""
import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from ai.evaluation import eval_demo_city as edc
from ai.evaluation.analytics_reference import haversine_m, hotspots, recurring_sites
from ai.training.src import build_demo_city as bdc
from ai.training.src.synthetic.city import LEGAL, NOW, TERMINAL, build_city
from ai.training.src.synthetic.city_checks import MINIMUMS, counts, recovery, validate_city

COMMITTED = edc.DEFAULT_DIR
B0_TINY = Path(__file__).resolve().parents[2] / "artifacts" / "fixtures" / "b0_tiny"


@pytest.fixture(scope="module")
def city():
    return build_city()


def test_the_city_is_deterministic_and_the_seed_matters(city):
    again = build_city()
    assert json.dumps(again, sort_keys=True) == json.dumps(city, sort_keys=True)
    other = build_city(seed=1, n_cases=520)
    assert [c["id"] for c in other["cases"]][:5] != [c["id"] for c in city["cases"]][:5] and len(other["cases"]) == 520


def test_the_city_meets_every_section_58_minimum_and_validates(city):
    assert validate_city(city) == []
    c = counts(city)
    for k, mn in MINIMUMS.items():
        assert c[k] >= mn, k
    assert c["wards"] == 10 and c["departments"] == 8 and c["cases"] >= 500
    assert c["reopened"] >= 20 and c["currently_reopened"] > 0 and c["rejected"] > 0 and c["open"] > 100 and c["resolved"] > 200
    assert c["active_incidents"] == 3 and c["incidents"] == 5


def test_everything_is_labelled_synthetic_and_demo_prefixed(city):
    for name in ("wards", "departments", "users", "cases", "report_signals", "case_relations", "status_events", "work_orders", "verifications", "incidents"):
        assert all(r["synthetic"] is True for r in city[name]), name
    assert all(c["public_case_id"].startswith("DEMO-2026-") for c in city["cases"]) and all(w["name"].startswith("Synthetic Ward") for w in city["wards"])
    assert all(u["name"].startswith("Synthetic") for u in city["users"])
    assert all("noreply" not in json.dumps(u) and "@" not in json.dumps(u) for u in city["users"])           # no contact data at all
    m = json.loads((COMMITTED / "manifest.json").read_text(encoding="utf-8"))
    assert m["synthetic"] is True and "SYNTHETIC" in m["notice"] and "not describe a real city" in m["notice"].replace("Nothing here describes a real city", "not describe a real city")


def test_reports_cover_four_languages_including_devanagari_and_hinglish(city):
    langs = counts(city)["multilingual_signals"]
    assert all(v >= 50 for v in langs.values()), langs
    assert any(any("ऀ" <= ch <= "ॿ" for ch in s["original_text"]) for s in city["report_signals"] if s["original_language"] in ("hi", "mr"))
    assert any(s["code_mixed"] for s in city["report_signals"])


def test_lifecycles_follow_the_state_machine_and_status_matches_the_last_event(city):
    by: dict = {}
    for e in city["status_events"]:
        by.setdefault(e["case_id"], []).append(e)
    cases = {c["id"]: c for c in city["cases"]}
    for cid, evs in by.items():
        assert evs[0]["to_state"] == "SUBMITTED"
        for a, b in zip(evs, evs[1:], strict=False):
            assert b["to_state"] in LEGAL[a["to_state"]] and b["at"] >= a["at"]
        assert cases[cid]["status"] == evs[-1]["to_state"]
        assert (cases[cid]["closed_at"] is not None) == (cases[cid]["status"] in TERMINAL)
    assert set(by) == set(cases)


def test_priority_and_sla_come_from_the_deterministic_rules_and_are_stable(city):
    r = edc.evaluate_triage_stability(city)
    assert r["n"] == len(city["cases"]) and r["mismatches"] == 0 and "AI never sets priority" in r["note"]


def test_planted_ground_truth_is_recoverable_by_the_reference_analytics(city):
    rec = recovery(city)
    assert rec["recurring"]["recall"] == 1.0 and rec["recurring"]["unexplained_by_any_planted_structure"] == 0 and rec["hotspots"]["recall"] == 1.0
    cases = {c["id"]: c for c in city["cases"]}
    for site in city["ground_truth"]["recurring_sites"]:
        sc = [cases[i] for i in site["case_ids"]]
        assert 4 <= len(sc) <= 6 and len({c["subcategory"] for c in sc}) == 1
        assert sum(c["status"] == "RESOLVED" for c in sc) >= 2 and sum(c["reopen_count"] > 0 for c in sc) >= 1                # the §38 example shape
    for h in city["ground_truth"]["hotspots"]:
        assert len(h["case_ids"]) >= 13
    for iid, ids in city["ground_truth"]["incident_cases"].items():
        assert len(ids) >= 8 and all(cases[i]["incident_id"] == iid for i in ids)
    for p in city["ground_truth"]["possible_duplicate_pairs"]:
        assert p["distance_m"] < 90
    for p in city["ground_truth"]["near_distinct_pairs"]:
        assert 60 < p["distance_m"] < 160


def test_validator_catches_corruption(city):
    def mutated(fn):
        d = copy.deepcopy(city)
        fn(d)
        return validate_city(d)
    assert any("dangling" in x for x in mutated(lambda d: d["cases"][0].__setitem__("ward_id", "nope")))
    assert any("not labelled synthetic" in x for x in mutated(lambda d: d["cases"][0].__setitem__("synthetic", False)))
    assert any("illegal transition" in x for x in mutated(lambda d: d["status_events"][2].__setitem__("to_state", "RESOLVED")))
    assert any("minimum not met" in x for x in mutated(lambda d: d.__setitem__("wards", d["wards"][:5])))
    assert any("sla_hours" in x for x in mutated(lambda d: d["cases"][0].__setitem__("sla_hours", 1)))
    assert any("closed_at inconsistent" in x for x in mutated(lambda d: next(c for c in d["cases"] if c["status"] == "RESOLVED").__setitem__("closed_at", None)))
    assert any("not DEMO-prefixed" in x for x in mutated(lambda d: d["cases"][0].__setitem__("public_case_id", "CC-REAL-1")))
    assert any("missing or empty" in x for x in validate_city({"cases": []}))


def test_committed_files_match_the_generator_and_their_manifest_hashes():
    assert bdc.main(["--out", str(COMMITTED), "--check"]) == 0
    m = json.loads((COMMITTED / "manifest.json").read_text(encoding="utf-8"))
    for name, meta in m["files"].items():
        b = (COMMITTED / name).read_bytes()
        assert hashlib.sha256(b).hexdigest() == meta["sha256"] and len(b) == meta["bytes"] < 1_000_000, name
    assert m["seed"] == bdc.DEFAULT_SEED and m["counts"]["cases"] == 560


def test_check_mode_detects_a_tampered_file(tmp_path):
    out = tmp_path / "city"
    assert bdc.main(["--out", str(out), "--cases", "520"]) == 0
    assert bdc.main(["--out", str(out), "--cases", "520", "--check"]) == 0
    (out / "cases.jsonl").write_text("{}\n", encoding="utf-8")
    assert bdc.main(["--out", str(out), "--cases", "520", "--check"]) == 1
    assert bdc.main(["--out", str(tmp_path / "x"), "--cases", "100"]) == 1                 # too small for the §58 minimums: refuses to write
    assert not (tmp_path / "x").exists()


# ------------------------------------------------------------------ reference analytics on hand-made cases
def mk(i, sub, lat, lon, days_ago, status="RESOLVED", reopen=0):
    return {"id": f"c{i}", "subcategory": sub, "location": {"latitude": lat, "longitude": lon}, "created_at": (NOW - timedelta(days=days_ago)).isoformat(), "status": status, "reopen_count": reopen}


def test_recurrence_requires_same_subcategory_radius_window_and_count():
    base = (19.07, 72.87)
    near = [mk(i, "pipe_leakage", base[0] + i * 0.0003, base[1], 20 + i * 30) for i in range(4)]          # ~33 m apart, within 240 d
    assert [s["n_cases"] for s in recurring_sites(near)] == [4]
    assert recurring_sites(near[:3]) == []                                                                   # too few
    assert recurring_sites([*near[:3], mk(9, "pothole", base[0], base[1], 25)]) == []                       # different subcategory
    far = [mk(i, "pipe_leakage", base[0] + i * 0.004, base[1], 20 + i * 30) for i in range(4)]            # ~445 m apart
    assert recurring_sites(far) == []
    old = [mk(i, "pipe_leakage", base[0], base[1], 10 + i * 100) for i in range(4)]                         # spread over 300 days
    assert recurring_sites(old) == [] and len(recurring_sites(old, window_days=400)) == 1
    s = recurring_sites([mk(0, "pipe_leakage", *base, 200), mk(1, "pipe_leakage", *base, 150, reopen=1), mk(2, "pipe_leakage", *base, 90, status="IN_PROGRESS"),
                         mk(3, "pipe_leakage", *base, 10)])[0]
    assert (s["n_resolved"], s["n_reopened"]) == (3, 1)


def test_hotspots_need_a_surge_against_the_baseline():
    base = (19.07, 72.87)
    surge = [mk(i, "garbage_overflow", base[0] + (i % 3) * 0.0002, base[1], 1 + i * 0.5) for i in range(10)]
    assert [h["recent_cases"] for h in hotspots(surge, NOW)] == [10]
    light = surge + [mk(100 + i, "garbage_overflow", base[0], base[1], 20 + i * 8) for i in range(10)]            # 10 baseline cases: the surge still stands out
    assert len(hotspots(light, NOW)) == 1 and hotspots(light, NOW)[0]["ratio_vs_baseline"] > 3
    steady = surge + [mk(100 + i, "garbage_overflow", base[0], base[1], 15 + i * 1.4) for i in range(60)]        # a heavy baseline (~0.67/day): no surge
    assert hotspots(steady, NOW) == []
    assert hotspots(surge[:5], NOW) == []
    assert haversine_m(base, (base[0] + 0.001, base[1])) == pytest.approx(111.2, abs=1)


# ------------------------------------------------------------------ evaluation plumbing
def test_demo_city_evaluation_runs_end_to_end_and_labels_everything_synthetic(tmp_path):
    out = tmp_path / "rep"
    assert edc.main(["--artifact", str(B0_TINY), "--out", str(out)]) == 0
    rep = json.loads((out / "demo_city_synthetic.json").read_text(encoding="utf-8"))
    assert rep["track"] == "synthetic" and rep["claims"]["real_world_accuracy_claim_allowed"] is False and "SYNTHETIC DATA ONLY" in rep["claims"]["banner"]
    r = rep["results"]
    assert r["intake_heldout_families"]["n"] > 50 and "text_split_pool == test" in r["intake_heldout_families"]["slice"]
    assert r["intake_all_reports_in_distribution_mixed"]["n"] == len(edc.load_city()["report_signals"]) and "optimistic" in r["intake_all_reports_in_distribution_mixed"]["slice"]
    assert r["fusion"]["auc_roc"] >= 0.95 and r["fusion"]["gate_recall_of_true_duplicates"] == 1.0 and r["fusion"]["by_pair_type"]["distinct_near"]["flagged_possible_duplicate"] == 0.0
    assert r["triage"]["mismatches"] == 0 and r["analytics_recovery"]["recurring"]["recall"] == 1.0 and r["analytics_recovery"]["hotspots"]["recall"] == 1.0
    assert (out / "demo_city_synthetic.md").read_text(encoding="utf-8").startswith("# Evaluation report")


def test_without_an_artifact_the_intake_part_is_skipped_not_invented(tmp_path):
    out = tmp_path / "rep"
    assert edc.main(["--out", str(out)]) == 0
    r = json.loads((out / "demo_city_synthetic.json").read_text(encoding="utf-8"))["results"]
    assert r["intake"].startswith("SKIPPED") and "intake_heldout_families" not in r and r["fusion"]["n_pairs"] > 100


def test_heldout_slice_contains_only_unseen_template_families():
    rows = edc.intake_rows(edc.load_city())
    held = [r for r in rows if r["split"] == "test"]
    assert held and all(r["family_id"].endswith(":4") for r in held) and not any(r["family_id"].endswith(":4") for r in rows if r["split"] != "test")


def test_timestamps_are_not_in_the_future_and_window_is_240_days(city):
    times = [datetime.fromisoformat(c["created_at"].replace("Z", "+00:00")) for c in city["cases"]]
    assert max(times) < NOW and min(times) >= NOW - timedelta(days=241) and times == sorted(times)
    assert all(datetime.fromisoformat(e["at"].replace("Z", "+00:00")) <= NOW.astimezone(timezone.utc) for e in city["status_events"])
