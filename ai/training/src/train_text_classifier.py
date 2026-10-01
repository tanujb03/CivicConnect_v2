"""B0: character n-gram TF-IDF + logistic regression (multilingual text classifier).

    python -m ai.training.src.train_text_classifier \
        --data ai/artifacts/datasets/synthetic_v1 --out ai/artifacts/civic_text_b0

The feature code is imported from ``ai.inference.local.featurizer`` so training
and serving share one implementation. Only the vocabulary/IDF fitting and the
linear weights are learned here. The script ends with a **parity check**: the
exported numpy artifact must reproduce scikit-learn's probabilities.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np

from ai.inference.config import load_taxonomy
from ai.inference.local.featurizer import CharNgramVectorizer, count_ngrams
from ai.inference.local.text_classifier import LocalTextClassifier
from ai.training.src.artifact_writer import write_classifier_artifact
from ai.training.src.io_utils import read_jsonl, sha256_file


def fit_vectorizer(texts: list[str], ngram_range=(2, 4), min_df: int = 2, max_features: int = 30000,
                   sublinear_tf: bool = True) -> CharNgramVectorizer:
    df: Counter = Counter()
    for t in texts:
        df.update(count_ngrams(t, ngram_range).keys())
    kept = [(g, c) for g, c in df.items() if c >= min_df]
    kept.sort(key=lambda gc: (-gc[1], gc[0]))           # deterministic: df desc, then lexicographic
    kept = sorted(kept[:max_features], key=lambda gc: gc[0])
    vocab = {g: i for i, (g, _) in enumerate(kept)}
    n = len(texts)
    idf = np.array([math.log((1 + n) / (1 + df[g])) + 1.0 for g in vocab], dtype=np.float32)
    return CharNgramVectorizer(vocab, idf, ngram_range, sublinear_tf)


def to_csr(vec: CharNgramVectorizer, texts: list[str]):
    from scipy.sparse import csr_matrix
    indptr, indices, data = [0], [], []
    for t in texts:
        idx, val = vec.transform_one(t)
        indices.append(idx)
        data.append(val)
        indptr.append(indptr[-1] + len(idx))
    return csr_matrix((np.concatenate(data) if data else np.empty(0), np.concatenate(indices) if indices else np.empty(0, dtype=np.int64),
                       np.array(indptr)), shape=(len(texts), vec.n_features))


def fit_temperature(logits: np.ndarray, y: np.ndarray) -> float:
    """Single-parameter temperature scaling by NLL grid search on held-out logits."""
    best_t, best = 1.0, float("inf")
    for t in np.arange(0.25, 6.01, 0.05):
        z = logits / t
        z = z - z.max(axis=1, keepdims=True)
        logp = z - np.log(np.exp(z).sum(axis=1, keepdims=True))
        nll = -logp[np.arange(len(y)), y].mean()
        if nll < best:
            best, best_t = nll, float(t)
    return round(best_t, 2)


def macro_f1(y_true: np.ndarray, y_pred: np.ndarray, k: int) -> float:
    f1s = []
    for c in range(k):
        tp = int(((y_pred == c) & (y_true == c)).sum())
        fp = int(((y_pred == c) & (y_true != c)).sum())
        fn = int(((y_pred != c) & (y_true == c)).sum())
        denom = 2 * tp + fp + fn
        f1s.append(2 * tp / denom if denom else 0.0)
    return float(np.mean(f1s))


def train(train_rows: list[dict], val_rows: list[dict], *, c_grid=(1.0, 3.0, 10.0, 30.0), ngram_range=(2, 4),
          min_df: int = 2, max_features: int = 30000, seed: int = 42, refit_on_trainval: bool = False) -> dict:
    from sklearn.linear_model import LogisticRegression

    t = load_taxonomy()
    labels = t.label_ids
    lab_idx = {l: i for i, l in enumerate(labels)}
    y_tr = np.array([lab_idx[f"{r['category']}/{r['subcategory']}"] for r in train_rows])
    y_va = np.array([lab_idx[f"{r['category']}/{r['subcategory']}"] for r in val_rows])
    missing = set(range(len(labels))) - set(y_tr.tolist())
    if missing:
        raise SystemExit(f"training data lacks labels: {[labels[i] for i in sorted(missing)]}")
    vec = fit_vectorizer([r["text"] for r in train_rows], ngram_range, min_df, max_features)
    X_tr, X_va = to_csr(vec, [r["text"] for r in train_rows]), to_csr(vec, [r["text"] for r in val_rows])

    best = None
    sweep = {}
    for C in c_grid:
        clf = LogisticRegression(C=C, max_iter=2000, random_state=seed)
        clf.fit(X_tr, y_tr)
        f1 = macro_f1(y_va, clf.predict(X_va), len(labels))
        sweep[str(C)] = round(f1, 4)
        if best is None or f1 > best[0] + 1e-9:
            best = (f1, C, clf)
    f1_val, C, clf = best
    logits_va = clf.decision_function(X_va)
    temp = fit_temperature(logits_va, y_va)
    pred_va = logits_va.argmax(1)
    metrics = {
        "val_accuracy": round(float((pred_va == y_va).mean()), 4),
        "val_macro_f1": round(f1_val, 4),
        "train_accuracy": round(float((clf.predict(X_tr) == y_tr).mean()), 4),
        "val_category_accuracy": round(float(np.mean([labels[p].split("/")[0] == labels[y].split("/")[0]
                                                      for p, y in zip(pred_va, y_va)])), 4),
        "c_sweep_val_macro_f1": sweep,
    }
    if refit_on_trainval:
        # Model selection (C) and calibration (T) used the unseen-family validation split; the shipped
        # model additionally learns from the validation families. Test families are never touched.
        all_rows = train_rows + val_rows
        y_all = np.concatenate([y_tr, y_va])
        vec = fit_vectorizer([r["text"] for r in all_rows], ngram_range, min_df, max_features)
        clf = LogisticRegression(C=C, max_iter=2000, random_state=seed).fit(to_csr(vec, [r["text"] for r in all_rows]), y_all)
        metrics["note"] = "val metrics are for the train-only model used for selection/calibration; shipped model refit on train+val"
    return {"vectorizer": vec, "clf": clf, "labels": labels, "temperature": temp, "metrics": metrics,
            "hyperparameters": {"C": C, "ngram_range": list(ngram_range), "min_df": min_df,
                                "max_features": max_features, "solver": "lbfgs", "seed": seed,
                                "refit_on_trainval": refit_on_trainval}}


def parity_check(out_dir: Path, result: dict, rows: list[dict], n: int = 200) -> float:
    """Exported numpy artifact must reproduce scikit-learn (temperature-scaled) probabilities."""
    loaded = LocalTextClassifier.load(out_dir)
    sub = rows[:n]
    X = to_csr(result["vectorizer"], [r["text"] for r in sub])
    z = result["clf"].decision_function(X) / result["temperature"]
    z = z - z.max(axis=1, keepdims=True)
    p_sk = np.exp(z) / np.exp(z).sum(axis=1, keepdims=True)
    worst = 0.0
    for i, r in enumerate(sub):
        p_np, _, _ = loaded.predict_proba(r["text"])
        worst = max(worst, float(np.abs(p_np - p_sk[i]).max()))
    if worst > 1e-4:
        raise SystemExit(f"PARITY FAILURE: numpy artifact differs from sklearn by {worst:.2e}")
    return worst


def run(data_dir: Path, out_root: Path, *, model_name: str = "civic_text_b0", version: str | None = None,
        seed: int = 42, refit_on_trainval: bool = True, **kw) -> Path:
    train_rows, val_rows = read_jsonl(data_dir / "train.jsonl"), read_jsonl(data_dir / "val.jsonl")
    ds_manifest = data_dir / "DATASET_MANIFEST.json"
    ds_sha = sha256_file(ds_manifest) if ds_manifest.exists() else "unknown"
    res = train(train_rows, val_rows, seed=seed, refit_on_trainval=refit_on_trainval, **kw)
    version = version or f"0.1.0+{ds_sha[:8]}"
    out_dir = out_root / version
    write_classifier_artifact(
        out_dir, model_name=model_name, version=version, taxonomy=load_taxonomy(), label_ids=res["labels"],
        vectorizer=res["vectorizer"], coef=res["clf"].coef_, intercept=res["clf"].intercept_,
        temperature=res["temperature"],
        training={"seed": seed, "dataset_manifest_sha256": ds_sha, "n_train": len(train_rows), "n_val": len(val_rows),
                  "hyperparameters": res["hyperparameters"], "split": "by template family and place pool"},
        metrics=res["metrics"])
    worst = parity_check(out_dir, res, val_rows)
    print(f"artifact: {out_dir}")
    print(json.dumps(res["metrics"], indent=2))
    print(f"parity (numpy vs sklearn) max |dp| = {worst:.2e}")
    return out_dir


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True, help="artifact root, e.g. ai/artifacts/civic_text_b0")
    ap.add_argument("--version", default=None)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-features", type=int, default=30000)
    ap.add_argument("--min-df", type=int, default=2)
    ap.add_argument("--no-refit-on-trainval", action="store_true", help="ship the train-only model")
    a = ap.parse_args(argv)
    run(a.data, a.out, version=a.version, seed=a.seed, max_features=a.max_features, min_df=a.min_df,
        refit_on_trainval=not a.no_refit_on_trainval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
