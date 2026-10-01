"""Regression floors on the SYNTHETIC held-out set (Section 57: 'AI changes require regression tests').

Needs the full B0 artifact (``ai/artifacts/civic_text_b0/<version>``, gitignored): produce it with
``python -m ai.training.src.train_text_classifier`` (or a Kaggle run) and unzip it there.
"""
import json
from pathlib import Path

import pytest

from ai.evaluation import eval_fusion, eval_intake, run_eval
from ai.inference.fusion.scoring import FusionWeights
from ai.inference.intake.service import IntakeService
from ai.inference.local.text_classifier import LocalTextClassifier

ART = Path(__file__).resolve().parents[2] / "artifacts"
FLOORS = json.loads((Path(__file__).resolve().parents[1] / "regression_floors.json").read_text(encoding="utf-8"))
DS = Path(run_eval.HERE) / "datasets"


def latest(sub: str):
    """Newest artifact folder by manifest mtime (robust to stale local folders)."""
    name = "fusion_weights.json" if "fusion" in sub else "manifest.json"
    d = sorted((p for p in (ART / sub).glob("*/") if (p / name).exists()), key=lambda p: (p / name).stat().st_mtime)
    return d[-1] if d else None


def test_b0_intake_meets_regression_floors():
    path = latest("civic_text_b0")
    if path is None or not (path / "weights.npz").exists():
        pytest.skip("full B0 artifact not present (gitignored); run the B0 training script or place the Kaggle output in ai/artifacts/civic_text_b0/")
    r = eval_intake.evaluate(IntakeService(None, LocalTextClassifier.load(path)), run_eval.read_jsonl(DS / "intake_eval.v1.jsonl"))
    f = FLOORS["intake_b0_local"]
    assert r["category_accuracy"] >= f["category_accuracy_min"], r["category_accuracy"]
    assert r["subcategory_accuracy"] >= f["subcategory_accuracy_min"], r["subcategory_accuracy"]
    assert r["subcategory_macro_f1"] >= f["subcategory_macro_f1_min"]
    assert r["calibration_ece_category"] <= f["calibration_ece_category_max"]
    assert r["structured_output_validity"] >= f["structured_output_validity_min"]


def test_calibrated_fusion_meets_regression_floors():
    path = latest("fusion_calibrator")
    if path is None:
        pytest.skip("fusion calibrator artifact not present")
    r = eval_fusion.evaluate(run_eval.read_jsonl(DS / "fusion_eval_pairs.v1.jsonl"), FusionWeights.load(path))
    f = FLOORS["fusion_calibrated_lexical"]
    assert r["auc_roc"] >= f["auc_roc_min"] and r["gate_recall_of_true_duplicates"] >= f["gate_recall_of_true_duplicates_min"]
