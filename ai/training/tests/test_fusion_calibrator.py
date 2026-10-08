import json

import numpy as np

from ai.inference.fusion.scoring import FusionWeights
from ai.training.src import train_fusion_calibrator as C
from ai.training.src.io_utils import read_jsonl
from ai.training.tests.optional_deps import requires_scipy


def test_auc_known_values():
    assert C.auc_roc(np.array([0.1, 0.2, 0.8, 0.9]), np.array([0, 0, 1, 1])) == 1.0
    assert C.auc_roc(np.array([0.9, 0.8, 0.2, 0.1]), np.array([0, 0, 1, 1])) == 0.0
    assert C.auc_roc(np.array([0.5, 0.5, 0.5, 0.5]), np.array([0, 1, 0, 1])) == 0.5


def test_prf_known_values():
    m = C.prf(np.array([0.9, 0.8, 0.3, 0.2]), np.array([1, 0, 1, 0]), 0.5)
    assert (m["tp"], m["fp"], m["fn"]) == (1, 1, 1) and m["precision"] == 0.5 and m["recall"] == 0.5


@requires_scipy
def test_constrained_fit_never_produces_negative_weights():
    rng = np.random.default_rng(1)
    X = rng.random((500, 4))
    y = (X[:, 1] * 3 - X[:, 0] * 2 + rng.normal(0, 0.3, 500) > 0.3).astype(float)   # feature 0 is anti-correlated
    b, w = C.fit_constrained_logistic(X, y, 0.01)
    assert (w >= -1e-9).all() and w[1] > 0.5 and w[0] < 0.05


def test_gating_drops_out_of_policy_pairs(small_dataset):
    pairs = read_jsonl(small_dataset / "pairs_val.jsonl")
    X, y, kept = C.pair_features(pairs)
    far = [p for p in pairs if p["pair_type"] in ("distinct_far", "recurrence_old")]
    assert len(kept) < len(pairs) and not any(p["pair_type"] == "distinct_far" for p in kept) and far
    assert X.shape == (len(kept), 4) and ((X >= 0) & (X <= 1)).all()


@requires_scipy
def test_calibration_writes_loadable_monotone_weights(small_dataset, tmp_path):
    out = C.run(small_dataset, tmp_path / "fw")
    w = FusionWeights.load(out)
    doc = json.loads((out / "fusion_weights.json").read_text(encoding="utf-8"))
    assert w.status == "calibrated_synthetic" and w.semantic_trained_on == "lexical" and doc["synthetic_data"] is True
    assert min(w.semantic, w.geospatial, w.temporal, w.category) >= 0 and w.geospatial > 0
    assert doc["metrics"]["val_auc_roc"] > 0.9 and doc["limitations"] and (out / "MODEL_CARD.md").exists()
    assert w.score(1, 1, 1, 1) > w.score(0, 0, 0, 0)
