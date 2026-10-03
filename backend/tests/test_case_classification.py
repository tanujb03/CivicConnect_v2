"""Cases created without a category: the local text classifier (M6 ONNX if AI_TEXT_ONNX_PATH is set, else B0) proposes one; a human's category is never overridden;
low confidence stays other/unclassified with a warning; the suggestion is stored as an AIAnalysis (source, model, confidence)."""
from __future__ import annotations

from pathlib import Path

import pytest

from ai.inference.local.text_classifier import LocalPrediction
from backend.services import classification
from backend.tests.helpers import case_body

REPO = Path(__file__).resolve().parents[2]


class FakeClassifier:
    model_name, model_version = "fake-m6", "9"

    def __init__(self, label="roads/pothole", cat_p=0.93, sub_p=0.9, abstain=False, boom=False):
        self.label, self.cat_p, self.sub_p, self.abstain, self.boom, self.seen = label, cat_p, sub_p, abstain, boom, []

    def predict(self, text, top_k=3, explain_k=5):
        self.seen.append(text)
        if self.boom:
            raise RuntimeError("model exploded")
        cat, _, sub = self.label.partition("/")
        return LocalPrediction(label_id=self.label, category=cat, subcategory=sub, category_probability=self.cat_p, subcategory_probability=self.sub_p,
                               top_k=[(self.label, self.sub_p), ("other/unclassified", 0.02)], abstained=self.abstain, model_name=self.model_name, model_version=self.model_version)


def _post(e, who="alice", **kw):
    body = case_body(e, **kw)
    for k in [k for k, v in kw.items() if v is None]:
        body.pop(k, None)
    r = e.client.post("/api/v1/cases", headers=e.idem(who), json=body)
    assert r.status_code in (200, 201), r.text
    return r.json()["case"]


def _analyses(e, case_id):
    from backend.models import AIAnalysis
    with e.session_factory() as db:
        return [(a.task_type, a.source, a.model, a.model_version, a.confidence, a.degraded, a.result_json, a.extra) for a in db.query(AIAnalysis).filter(AIAnalysis.case_id == case_id)
                if a.task_type == "classification"]


def _events(e, case_id):
    from backend.models import CaseEvent
    with e.session_factory() as db:
        return [(x.event_type, x.visibility, x.event_metadata) for x in db.query(CaseEvent).filter(CaseEvent.case_id == case_id).order_by(CaseEvent.seq)]


@pytest.fixture
def clf(monkeypatch):
    c = FakeClassifier()
    monkeypatch.setattr(classification, "get_classifier", lambda: c)
    return c


def test_confident_suggestion_fills_the_missing_category_and_is_stored_with_source_model_confidence(staffed, clf):
    e = staffed
    c = _post(e, category=None, subcategory=None, description="Huge pothole outside the school gate")
    assert (c["category"], c["subcategory"]) == ("roads", "pothole") and c["department_id"] == "road_maintenance"
    [(task, source, model, version, conf, degraded, result, extra)] = _analyses(e, c["id"])
    assert (task, source, model, version, degraded) == ("classification", "local_classifier", "fake-m6", "9", False)
    assert conf == pytest.approx(0.93) and result["applied_category"] == "roads" and result["suggested"]["applied"] is True and result["top_k"][0][0] == "roads/pothole"
    assert "Huge pothole outside the school gate" in clf.seen[0]
    ev = [x for x in _events(e, c["id"]) if x[0] == "CATEGORY_SUGGESTED"]
    assert len(ev) == 1 and ev[0][1] == "INTERNAL" and ev[0][2]["applied"] is True


def test_the_suggestion_is_internal_citizens_do_not_see_it_in_the_timeline(staffed, clf):
    e = staffed
    c = _post(e, category=None, subcategory=None)
    own = e.client.get(f"/api/v1/cases/{c['id']}", headers=e.headers("alice")).json()
    assert "CATEGORY_SUGGESTED" not in [t["event_type"] for t in own["timeline"]]
    staff = e.client.get(f"/api/v1/cases/{c['id']}", headers=e.headers("admin")).json()
    assert "CATEGORY_SUGGESTED" in [t["event_type"] for t in staff["timeline"]]


def test_a_category_given_by_a_human_is_never_overridden_even_when_the_classifier_disagrees(staffed, monkeypatch):
    e = staffed
    c = FakeClassifier(label="sanitation/garbage_overflow", cat_p=0.99, sub_p=0.99)
    monkeypatch.setattr(classification, "get_classifier", lambda: c)
    case = _post(e, category="roads", subcategory="pothole")
    assert (case["category"], case["subcategory"]) == ("roads", "pothole")
    assert c.seen == [] and _analyses(e, case["id"]) == []                       # not even asked
    only_category = _post(e, category="water_supply", subcategory=None, client_case_id="x2")
    assert only_category["category"] == "water_supply" and _analyses(e, only_category["id"]) == []
    explicit_other = _post(e, category="other", subcategory=None, client_case_id="x3")
    assert explicit_other["category"] == "other" and c.seen == []


def test_low_confidence_stays_other_unclassified_with_a_warning(staffed, monkeypatch):
    e = staffed
    monkeypatch.setattr(classification, "get_classifier", lambda: FakeClassifier(cat_p=0.40, sub_p=0.30))
    case = _post(e, category=None, subcategory=None)
    assert (case["category"], case["subcategory"]) == ("other", "unclassified")
    [(_, _, _, _, conf, degraded, result, extra)] = _analyses(e, case["id"])
    assert degraded is True and conf == pytest.approx(0.40) and result["suggested"]["applied"] is False and result["suggested"]["label_id"] == "roads/pothole"
    assert any(w.startswith("LOW_CONFIDENCE") for w in result["warnings"]) and extra["warnings"] == result["warnings"]
    ev = [x for x in _events(e, case["id"]) if x[0] == "CATEGORY_SUGGESTED"][0]
    assert ev[2]["applied"] is False and ev[2]["warnings"]


def test_a_confident_category_with_an_unsure_subcategory_sets_only_the_category(staffed, monkeypatch):
    e = staffed
    monkeypatch.setattr(classification, "get_classifier", lambda: FakeClassifier(cat_p=0.9, sub_p=0.3))
    case = _post(e, category=None, subcategory=None)
    assert (case["category"], case["subcategory"]) == ("roads", None)
    assert any("subcategory confidence" in w for w in _analyses(e, case["id"])[0][6]["warnings"])


@pytest.mark.parametrize("make,warning", [(lambda: None, "NO_AI_AVAILABLE"), (lambda: FakeClassifier(boom=True), "CLASSIFIER_FAILED"), (lambda: FakeClassifier(abstain=True), "LOW_CONFIDENCE"),
                                          (lambda: FakeClassifier(label="other/unclassified", cat_p=0.97, sub_p=0.97), "LOW_CONFIDENCE")])
def test_no_classifier_a_failing_one_or_no_opinion_never_fails_case_creation(staffed, monkeypatch, make, warning):
    e = staffed
    monkeypatch.setattr(classification, "get_classifier", make)
    case = _post(e, category=None, subcategory=None)
    assert (case["category"], case["subcategory"]) == ("other", "unclassified") and case["status"] == "NEEDS_REVIEW"
    [(_, _, _, _, _, degraded, result, _)] = _analyses(e, case["id"])
    assert degraded is True and any(w.startswith(warning) for w in result["warnings"])


def test_an_evidence_only_case_has_no_text_to_classify_and_says_so(staffed, clf):
    from backend.tests.helpers import upload
    e = staffed
    ev = upload(e, "alice")
    r = e.client.post("/api/v1/cases", headers=e.idem("alice"), json={"location": e.where, "evidence_ids": [ev["id"]]})
    assert r.status_code in (200, 201), r.text
    case = r.json()["case"]
    assert case["category"] == "other" and clf.seen == []
    assert any(w.startswith("NO_TEXT_TO_CLASSIFY") for w in _analyses(e, case["id"])[0][6]["warnings"])


def test_a_retried_offline_create_does_not_classify_twice(staffed, clf):
    e = staffed
    a = _post(e, category=None, subcategory=None, client_case_id="offline-1")
    b = _post(e, category=None, subcategory=None, client_case_id="offline-1")
    assert a["id"] == b["id"] and len(clf.seen) == 1 and len(_analyses(e, a["id"])) == 1


# ---- the REAL loaders: M6 ONNX when AI_TEXT_ONNX_PATH is set, else B0 --------------------------------------------------------------------------------------------
def _fresh_gateway(monkeypatch, **env):
    from backend.ai_gateway import configure_gateway
    from backend.ai_gateway.sql import build_sql_gateway
    for k, v in env.items():
        monkeypatch.setenv(k, str(v))
    configure_gateway(build_sql_gateway())


def test_m6_onnx_is_used_when_ai_text_onnx_path_is_set(staffed, monkeypatch, tmp_path):
    pytest.importorskip("onnx")
    pytest.importorskip("onnxruntime")
    pytest.importorskip("tokenizers")
    from backend.tests.onnx_artifacts import write_m6_artifact
    e = staffed
    _fresh_gateway(monkeypatch, AI_TEXT_ONNX_PATH=write_m6_artifact(tmp_path / "m6", favour="sanitation/garbage_overflow"))
    case = _post(e, category=None, subcategory=None, description="garbage near the market")
    assert (case["category"], case["subcategory"]) == ("sanitation", "garbage_overflow")
    [(_, source, model, version, conf, *_)] = _analyses(e, case["id"])
    assert (source, model, version) == ("local_m6", "civic-text-m6", "test-1") and conf > 0.9


def test_b0_is_the_fallback_when_no_m6_is_configured(staffed, monkeypatch):
    fixture = REPO / "ai" / "artifacts" / "fixtures" / "b0_tiny"
    if not (fixture / "manifest.json").exists():
        pytest.skip("B0 fixture artifact not present")
    e = staffed
    _fresh_gateway(monkeypatch, AI_LOCAL_CLASSIFIER_PATH=fixture)
    case = _post(e, category=None, subcategory=None, description="there is a big pothole in the road near the school")
    [(_, source, model, version, conf, degraded, result, _)] = _analyses(e, case["id"])
    assert source == "local_b0" and model and conf is not None and result["top_k"]
    assert case["category"] == result["applied_category"]                       # whatever the tiny model decided is what was applied
