import json
import shutil

import numpy as np
import pytest

from ai.inference.errors import ArtifactError
from ai.inference.local.text_classifier import LocalTextClassifier

from .conftest import POTHOLE_TEXT


def test_golden_predictions_reproduce_from_committed_artifact(tiny_classifier, tiny_artifact_dir):
    golden = json.loads((tiny_artifact_dir / "golden.json").read_text(encoding="utf-8"))
    assert len(golden) >= 5
    for g in golden:
        p = tiny_classifier.predict(g["text"])
        assert p.label_id == g["label_id"] and p.abstained == g["abstained"], g["text"]
        assert abs(p.subcategory_probability - g["subcategory_probability"]) < 5e-4


def test_probabilities_are_a_distribution(tiny_classifier):
    probs, idx, val = tiny_classifier.predict_proba(POTHOLE_TEXT)
    assert probs.shape == (len(tiny_classifier.label_ids),)
    assert abs(float(probs.sum()) - 1.0) < 1e-6 and (probs >= 0).all()


def test_prediction_structure(tiny_classifier):
    p = tiny_classifier.predict(POTHOLE_TEXT, top_k=3)
    assert p.category == "roads" and p.subcategory == "pothole" and p.label_id == "roads/pothole"
    assert p.category_probability >= p.subcategory_probability
    assert [lid for lid, _ in p.top_k][0] == p.label_id and len(p.top_k) == 3
    assert all(a[1] >= b[1] for a, b in zip(p.top_k, p.top_k[1:]))
    assert p.explanation_terms and all(len(t) >= 3 for t in p.explanation_terms)
    assert p.model_name == "civic_text_b0_fixture"


@pytest.mark.parametrize("text", ["", "zzzz qqqq", "!!!"])
def test_unknown_input_abstains(tiny_classifier, text):
    p = tiny_classifier.predict(text)
    assert p.abstained and p.explanation_terms == []


def test_prediction_is_deterministic(tiny_classifier):
    a, b = tiny_classifier.predict(POTHOLE_TEXT), tiny_classifier.predict(POTHOLE_TEXT)
    assert a == b


@pytest.fixture
def copy_artifact(tiny_artifact_dir, tmp_path):
    dst = tmp_path / "art"
    shutil.copytree(tiny_artifact_dir, dst)
    return dst


def test_missing_manifest(tmp_path):
    with pytest.raises(ArtifactError, match="manifest"):
        LocalTextClassifier.load(tmp_path)


def test_checksum_mismatch_is_detected(copy_artifact):
    w = copy_artifact / "weights.npz"
    w.write_bytes(w.read_bytes()[:-8] + b"corrupt!")
    with pytest.raises(ArtifactError, match="checksum"):
        LocalTextClassifier.load(copy_artifact)


def test_schema_version_mismatch(copy_artifact):
    m = json.loads((copy_artifact / "manifest.json").read_text(encoding="utf-8"))
    m["artifact_schema"] = "civic-text-classifier/99"
    (copy_artifact / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(ArtifactError, match="schema"):
        LocalTextClassifier.load(copy_artifact)


def test_normaliser_mismatch(copy_artifact):
    m = json.loads((copy_artifact / "manifest.json").read_text(encoding="utf-8"))
    m["vectorizer"]["normalizer"] = "civic-norm/0"
    (copy_artifact / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(ArtifactError, match="normaliser"):
        LocalTextClassifier.load(copy_artifact)


def test_label_not_in_taxonomy_is_rejected(copy_artifact):
    m = json.loads((copy_artifact / "manifest.json").read_text(encoding="utf-8"))
    m["label_ids"][0] = "roads/not_a_real_subcategory"
    (copy_artifact / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(ArtifactError, match="taxonomy"):
        LocalTextClassifier.load(copy_artifact)


def test_missing_file_is_rejected(copy_artifact):
    (copy_artifact / "vocab.json").unlink()
    with pytest.raises(ArtifactError, match="missing"):
        LocalTextClassifier.load(copy_artifact)


def test_array_shape_mismatch_is_rejected(copy_artifact):
    import hashlib
    with np.load(copy_artifact / "weights.npz") as w:
        arrs = {k: w[k] for k in w.files}
    arrs["coef"] = arrs["coef"][:, :-1]
    np.savez(copy_artifact / "weights.npz", **arrs)
    m = json.loads((copy_artifact / "manifest.json").read_text(encoding="utf-8"))
    m["files"]["weights.npz"] = hashlib.sha256((copy_artifact / "weights.npz").read_bytes()).hexdigest()
    (copy_artifact / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(ArtifactError, match="shape"):
        LocalTextClassifier.load(copy_artifact)


def test_manifest_flags_synthetic_and_lists_limitations(tiny_artifact_dir):
    m = json.loads((tiny_artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    assert m["synthetic_data"] is True and m["limitations"] and "SYNTHETIC" in m["limitations"][0].upper()
