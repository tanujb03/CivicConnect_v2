"""AI-4 synthetic scenarios: reproducibility, labelling, and the baseline's structural guarantees."""
import json
from collections import Counter

from ai.evaluation import eval_resolution
from ai.evaluation.run_eval import HERE
from ai.training.src import build_resolution_scenarios as build
from ai.training.src.synthetic.resolution import ARCHETYPES

FLOORS = json.loads((HERE / "regression_floors.json").read_text(encoding="utf-8"))["resolution_baseline"]
ROWS = eval_resolution.load()


def test_committed_scenarios_are_reproducible_from_the_demo_city():
    for name, content in build.render(build.DEFAULT_SEED, 240).items():
        assert (eval_resolution.DEFAULT_DIR / name).read_bytes() == content, name


def test_scenarios_are_labelled_synthetic_and_internally_consistent():
    assert len(ROWS) == 240 and all(r["synthetic"] for r in ROWS)
    manifest = json.loads((eval_resolution.DEFAULT_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["synthetic"] and "NO images" in manifest["notice"]
    for r in ROWS:
        assert r["has_resolution_photo"] == (r["archetype"] != "no_after_evidence")
        assert r["citizen_verification"] in (None, "YES", "PARTIAL", "STILL_OCCURRING", "NO")
        assert (r["detectable_by"] == "none_needed") == (not r["truly_unresolved"])
        if r["detectable_by"] == "citizen_signal":
            assert r["citizen_verification"] in ("PARTIAL", "STILL_OCCURRING", "NO")
        else:
            assert r["citizen_verification"] in (None, "YES")
    assert set(Counter(r["archetype"] for r in ROWS)) == {a[0] for a in ARCHETYPES}


def test_baseline_meets_structural_floors_and_is_honest_about_what_it_cannot_see():
    r = eval_resolution.evaluate(ROWS)
    assert r["unresolved_by_detectable_signal"]["citizen_signal"]["flagged_unresolved"] >= FLOORS["citizen_signal_flag_recall_min"]
    assert r["unresolved_flag_false_positive_rate"] <= FLOORS["unresolved_flag_false_positive_rate_max"]
    assert r["verification_request_recall_of_unresolved"] >= FLOORS["verification_request_recall_of_unresolved_min"]
    assert r["insufficient_evidence_correct_when_no_resolution_photo"] >= FLOORS["insufficient_evidence_correct_min"]
    assert r["monotonic_violations_with_optimistic_ai"] <= FLOORS["monotonic_violations_max"]
    assert r["autonomous_closure_allowed_any"] is False
    # the baseline does NOT read note text or pixels: silent unresolved cases are not flagged, only routed to the citizen verification step
    assert r["unresolved_by_detectable_signal"]["notes_text"]["flagged_unresolved"] == 0.0
    assert r["unresolved_by_detectable_signal"]["images_only"]["flagged_unresolved"] == 0.0
    assert "multimodal provider comparison (needs real before/after images + a configured model)" in r["not_evaluated"]
