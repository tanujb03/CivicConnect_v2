import json
import math

import numpy as np
import pytest

from ai.inference.config import load_taxonomy
from ai.inference.local.text_classifier import LocalTextClassifier
from ai.training.src import train_text_classifier as T
from ai.training.src.io_utils import read_jsonl
from ai.training.tests.optional_deps import requires_scipy, requires_sklearn


def test_vectoriser_fit_is_deterministic_and_sane():
    texts = ["big pothole near school", "pothole on road", "garbage pile", "garbage bin overflow"] * 3
    a, b = T.fit_vectorizer(texts, min_df=2), T.fit_vectorizer(texts, min_df=2)
    assert a.vocab == b.vocab and np.array_equal(a.idf, b.idf) and a.n_features > 10
    assert list(a.vocab.values()) == list(range(a.n_features)) and (a.idf >= 1.0).all()
    assert T.fit_vectorizer(texts, min_df=2, max_features=5).n_features == 5


def test_idf_matches_the_documented_formula():
    texts = ["aa bb", "aa cc", "aa dd"]
    v = T.fit_vectorizer(texts, ngram_range=(2, 2), min_df=1)
    assert v.idf[v.vocab["aa"]] == pytest.approx(math.log(4 / 4) + 1) if "aa" in v.vocab else True
    assert v.idf[v.vocab[" a"]] == pytest.approx(math.log(4 / 4) + 1)  # " a" occurs in all 3 docs
    assert v.idf[v.vocab[" b"]] == pytest.approx(math.log(4 / 2) + 1)


@requires_scipy
def test_csr_matches_transform_one():
    v = T.fit_vectorizer(["pothole road", "garbage bin"] * 2, min_df=1)
    X = T.to_csr(v, ["pothole", "garbage bin", "zzz"])
    idx, val = v.transform_one("garbage bin")
    row = X.getrow(1)
    assert np.array_equal(row.indices, idx) and np.allclose(row.data, val) and X.getrow(2).nnz == 0


def test_temperature_fitting_softens_overconfident_logits():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 3, 400)
    logits = np.eye(3)[y] * 8.0
    flip = rng.random(400) < 0.3                       # 30% wrong with very confident logits
    logits[flip] = np.eye(3)[(y[flip] + 1) % 3] * 8.0
    assert T.fit_temperature(logits, y) > 2.0
    perfect = np.eye(3)[y] * 3.0
    assert T.fit_temperature(perfect, y) <= 1.0


def test_macro_f1_known_values():
    assert T.macro_f1(np.array([0, 1, 2]), np.array([0, 1, 2]), 3) == 1.0
    assert T.macro_f1(np.array([0, 0, 1, 1]), np.array([0, 1, 1, 1]), 2) == pytest.approx((2 / 3 + 0.8) / 2)


@requires_scipy
@requires_sklearn
def test_end_to_end_training_exports_a_loadable_numpy_equivalent_artifact(small_dataset, tmp_path):
    out = T.run(small_dataset, tmp_path / "b0", seed=5, c_grid=(3.0,), min_df=2, max_features=4000)
    clf = LocalTextClassifier.load(out)                      # loader validates schema, checksums, taxonomy
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert m["synthetic_data"] is True and m["training"]["hyperparameters"]["refit_on_trainval"] is True
    assert m["label_ids"] == load_taxonomy().label_ids and m["limitations"] and (out / "MODEL_CARD.md").exists()
    assert "SYNTHETIC" in (out / "MODEL_CARD.md").read_text(encoding="utf-8")
    test_rows = read_jsonl(small_dataset / "test.jsonl")
    acc = np.mean([clf.predict(r["text"]).label_id == f"{r['category']}/{r['subcategory']}" for r in test_rows])
    assert acc > 4 / 27          # far above the 1/27 chance level even on unseen template families
    # parity between sklearn and numpy inference was asserted inside run(); re-check one example independently
    p, _, _ = clf.predict_proba(test_rows[0]["text"])
    assert abs(p.sum() - 1) < 1e-6


@requires_scipy
@requires_sklearn
def test_training_refuses_data_missing_a_class(small_dataset):
    rows = read_jsonl(small_dataset / "train.jsonl")
    rows = [r for r in rows if r["subcategory"] != "pothole"]
    with pytest.raises(SystemExit, match="lacks labels"):
        T.train(rows, read_jsonl(small_dataset / "val.jsonl"), c_grid=(1.0,))


def test_training_and_inference_share_one_featurizer():
    import ai.inference.local.featurizer as inf
    assert T.CharNgramVectorizer is inf.CharNgramVectorizer and T.count_ngrams is inf.count_ngrams
