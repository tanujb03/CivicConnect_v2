import json
from pathlib import Path

import pytest

from ai.evaluation import eval_fusion, eval_intake, run_eval
from ai.inference.fusion.scoring import FusionWeights
from ai.inference.intake.service import IntakeService
from ai.inference.local.text_classifier import LocalTextClassifier
from ai.inference.providers.fake import FakeProvider

AI_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = AI_ROOT / "artifacts" / "fixtures" / "b0_tiny"
DS = Path(run_eval.HERE) / "datasets"


def intake_rows():
    return run_eval.read_jsonl(DS / "intake_eval.v1.jsonl")


@pytest.fixture(scope="module")
def intake_result():
    svc = IntakeService(None, LocalTextClassifier.load(FIXTURE))
    return eval_intake.evaluate(svc, intake_rows())


def test_intake_evaluation_produces_all_section_57_metrics(intake_result):
    r = intake_result
    for k in ("category_accuracy", "subcategory_accuracy", "subcategory_macro_f1", "routing_accuracy_department", "severity_agreement",
              "calibration_ece_category", "structured_output_validity", "degraded_rate", "coverage_at_threshold"):
        assert 0 <= r[k] <= 1, k
    assert r["n"] == len(intake_rows()) and r["held_out_families"] == 108
    assert set(r["by_language"]) == {"en", "hi", "mr", "hi-Latn"} and r["top_confusions"]
    assert "CIRCULAR" in r["severity_note"]                       # severity metric is honestly labelled
    assert r["subcategory_accuracy"] > 1 / 27                      # even the tiny fixture beats chance


def test_degraded_rate_is_reported_for_the_local_fallback_path(intake_result):
    assert intake_result["degraded_rate"] == 1.0 and set(intake_result["sources"]) <= {"local_fallback", "none"}


def test_routing_accuracy_follows_category_accuracy_for_valid_predictions(intake_result):
    assert intake_result["routing_accuracy_department"] >= intake_result["category_accuracy"] - 0.2


def test_provider_system_can_be_evaluated_with_a_scripted_provider():
    scripted = {"title": "t", "description": "d", "category": "roads", "subcategory": "pothole", "severity": "LOW", "language": "en",
                "transcript": None, "confidence": 0.9, "reasons": [], "image_observations": []}
    res = eval_intake.evaluate(IntakeService(FakeProvider(structured={"intake": scripted})), intake_rows()[:30])
    assert res["degraded_rate"] == 0.0 and res["sources"] == {"provider": 30}


def test_fusion_evaluation_on_committed_pairs():
    pairs = run_eval.read_jsonl(DS / "fusion_eval_pairs.v1.jsonl")
    r = eval_fusion.evaluate(pairs)
    assert r["n_gated_in"] + r["negatives_removed_by_gate"] == len(pairs) and r["gate_recall_of_true_duplicates"] == 1.0
    assert r["auc_roc"] > 0.85 and r["weights_status"] == "uncalibrated_prior" and "SYNTHETIC" in r["caveat"]
    assert {"same_language", "cross_language"} <= set(r) and r["by_pair_type"]["duplicate"]["flagged_possible_duplicate"] > 0


def test_fusion_evaluation_with_calibrated_weights():
    pairs = run_eval.read_jsonl(DS / "fusion_eval_pairs.v1.jsonl")
    w = FusionWeights(-13.7, 0.0, 8.2, 1.4, 7.3, status="calibrated_synthetic", semantic_trained_on="lexical", version="t")
    r = eval_fusion.evaluate(pairs, w)
    assert r["weights_status"] == "calibrated_synthetic" and r["auc_roc"] > 0.9


def test_cli_writes_a_report_with_disclaimer_dataset_hash_and_artifact(tmp_path):
    rc = run_eval.main(["--task", "intake", "--system", "local", "--artifact", str(FIXTURE), "--out", str(tmp_path), "--name", "t"])
    assert rc == 0
    rep = json.loads((tmp_path / "t.json").read_text(encoding="utf-8"))
    assert "SYNTHETIC" in rep["disclaimer"] and rep["dataset"]["sha256"] and rep["artifact"].startswith("civic_text_b0_fixture@fixture-1")
    md = (tmp_path / "t.md").read_text(encoding="utf-8")
    assert "SYNTHETIC" in md and "By language" in md and "Top confusions" in md


def test_provider_evaluation_without_credentials_is_skipped_and_writes_nothing(tmp_path, monkeypatch, capsys):
    for k in ("OPENAI_API_KEY", "AI_INTAKE_MODEL"):
        monkeypatch.delenv(k, raising=False)
    rc = run_eval.main(["--task", "intake", "--system", "provider", "--out", str(tmp_path)])
    assert rc == 2 and not list(tmp_path.iterdir()) and "SKIPPED" in capsys.readouterr().err


def test_local_system_requires_an_artifact(tmp_path, capsys):
    assert run_eval.main(["--task", "intake", "--system", "local", "--out", str(tmp_path)]) == 2
