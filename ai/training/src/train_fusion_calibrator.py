"""Fit calibrated combined-score weights for AI-2 case fusion.

    python -m ai.training.src.train_fusion_calibrator \
        --data ai/artifacts/datasets/synthetic_v1 --out ai/artifacts/fusion_calibrator

A logistic regression over four deterministic signals (semantic, geospatial,
temporal, category) on gated candidate pairs. Signals are computed with the
exact inference-layer functions, so training and serving agree.

``--semantic-mode lexical`` (default, no credentials) uses the char-trigram
lexical signal. ``--semantic-mode provider`` computes real embeddings through
``OpenAIProvider`` (needs OPENAI_API_KEY + AI_EMBEDDING_MODEL) and fits the weights
for that signal — recommended before relying on embedding-based fusion.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ai.inference.config import load_fusion_policy
from ai.inference.fusion.scoring import WEIGHTS_SCHEMA, FusionWeights
from ai.inference.fusion.service import FusionService
from ai.inference.fusion.similarity import (
    category_signal,
    cosine,
    geospatial_signal,
    lexical_similarity,
    temporal_signal,
)
from ai.inference.schemas import FusionCase
from ai.training.src.io_utils import git_sha, read_jsonl, runtime_info, sha256_file


def _case(d: dict) -> FusionCase:
    return FusionCase(case_id=d["case_id"], category=d["category"], subcategory=d["subcategory"],
                      latitude=d["latitude"], longitude=d["longitude"],
                      created_at=datetime.fromisoformat(d["created_at"]), text=d["text"])


def provider_embeddings(texts: list[str]) -> dict[str, list[float]]:
    from ai.inference.config import ProviderSettings
    from ai.inference.providers.openai_provider import OpenAIProvider
    prov = OpenAIProvider(ProviderSettings.from_env())
    uniq = sorted(set(texts))
    res = prov.embed(uniq)
    return dict(zip(uniq, res.vectors))


def local_embeddings(texts: list[str], embed_onnx: Path) -> dict[str, list[float]]:
    """Embeddings from the exported local multilingual encoder (M7, ONNX on CPU): free, offline, cross-language."""
    from ai.training.src.text_model.runtime import load_backend_text_model
    emb = load_backend_text_model().OnnxEmbedder(embed_onnx)
    uniq = sorted(set(texts))
    return dict(zip(uniq, emb.embed(uniq)))


def pair_features(pairs: list[dict], semantic_mode: str = "lexical", emb: dict[str, list[float]] | None = None):
    """Return (X, y, kept_pairs) for pairs that pass the deterministic candidate gate."""
    svc = FusionService()
    cg = svc.policy["candidate_generation"]
    X, y, kept = [], [], []
    for p in pairs:
        a, b = _case(p["a"]), _case(p["b"])
        ok, d, age_h = svc.in_policy(a, b)
        if not ok:
            continue
        sem = (cosine(emb[p["a"]["text"]], emb[p["b"]["text"]]) if semantic_mode in ("provider", "local") and emb
               else lexical_similarity(a.text, b.text))
        X.append([sem, geospatial_signal(d, cg["radius_m"]), temporal_signal(age_h, cg["time_window_days"]),
                  category_signal(a.category, a.subcategory, b.category, b.subcategory)])
        y.append(p["label"])
        kept.append(p)
    return np.array(X), np.array(y), kept


def auc_roc(scores: np.ndarray, y: np.ndarray) -> float:
    order = np.argsort(scores, kind="stable")
    ranks = np.empty(len(scores))
    s = scores[order]
    i = 0
    while i < len(s):  # average ranks for ties
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    pos = y == 1
    n1, n0 = int(pos.sum()), int((~pos).sum())
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)) if n1 and n0 else float("nan")


def prf(scores: np.ndarray, y: np.ndarray, thr: float) -> dict:
    pred = scores >= thr
    tp, fp, fn = int((pred & (y == 1)).sum()), int((pred & (y == 0)).sum()), int((~pred & (y == 1)).sum())
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"threshold": round(float(thr), 4), "precision": round(p, 4), "recall": round(r, 4),
            "f1": round(2 * p * r / (p + r), 4) if p + r else 0.0, "tp": tp, "fp": fp, "fn": fn}


def logloss(z: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean(np.logaddexp(0, z) - y * z))


def fit_constrained_logistic(X: np.ndarray, y: np.ndarray, l2: float) -> tuple[float, np.ndarray]:
    """Logistic regression with NON-NEGATIVE feature weights (every signal is monotone: more similar /
    closer / more recent / same category can never lower the duplicate score) and an L2 penalty."""
    from scipy.optimize import minimize

    d = X.shape[1]

    def f(theta):
        b, w = theta[0], theta[1:]
        z = X @ w + b
        loss = logloss(z, y) + 0.5 * l2 * float(w @ w)
        pr = 1.0 / (1.0 + np.exp(-z))
        g_w = X.T @ (pr - y) / len(y) + l2 * w
        return loss, np.concatenate([[float(np.mean(pr - y))], g_w])

    res = minimize(f, np.zeros(d + 1), jac=True, method="L-BFGS-B", bounds=[(None, None)] + [(0.0, None)] * d)
    return float(res.x[0]), res.x[1:]


def _trained_on(pairs: list[dict], kind: str) -> dict:
    srcs: dict[str, dict] = {}
    for p in pairs:
        pv = p.get("provenance") or {}
        sid = pv.get("source_id", "synthetic_civic" if kind == "synthetic" else "unknown")
        d = srcs.setdefault(sid, {"n": 0, "license_verified": bool(pv.get("license_verified", kind == "synthetic")),
                                  "kind": pv.get("kind", kind)})
        d["n"] += 1
    return {"kind": kind, "sources": srcs}


def run(data_dir: Path | None, out_root: Path, *, semantic_mode: str = "lexical", version: str | None = None,
        l2_grid=(0.001, 0.01, 0.1, 1.0), train_pairs: Path | None = None, val_pairs: Path | None = None,
        data_kind: str = "synthetic", embed_onnx: Path | None = None) -> Path:
    """``data_kind='real'`` fits on REAL agency-linked pairs (``train_pairs``/``val_pairs`` from
    ``data_sources.cli pairs``); the weights are then labelled ``calibrated_real`` with their provenance."""

    if data_kind == "real":
        if not (train_pairs and val_pairs):
            raise SystemExit("--kind real needs --pairs-train and --pairs-val (real pairs, split by holdout)")
        tr, va = read_jsonl(train_pairs), read_jsonl(val_pairs)
        if any((p.get("provenance") or {}).get("kind") != "real_public" for p in tr + va):
            raise SystemExit("--kind real requires every pair to carry real_public provenance")
    else:
        tr, va = read_jsonl(data_dir / "pairs_train.jsonl"), read_jsonl(data_dir / "pairs_val.jsonl")
    emb = None
    if semantic_mode == "provider":
        emb = provider_embeddings([p[s]["text"] for p in tr + va for s in ("a", "b")])
    elif semantic_mode == "local":
        if embed_onnx is None:
            raise SystemExit("--semantic-mode local needs --embed-onnx <exported embedder dir>")
        emb = local_embeddings([p[s]["text"] for p in tr + va for s in ("a", "b")], embed_onnx)
    X_tr, y_tr, _ = pair_features(tr, semantic_mode, emb)
    X_va, y_va, _ = pair_features(va, semantic_mode, emb)
    best = None
    for l2 in l2_grid:  # regularisation chosen by validation log-loss (not F1)
        b, w_ = fit_constrained_logistic(X_tr, y_tr, l2)
        ll = logloss(X_va @ w_ + b, y_va)
        if best is None or ll < best[0] - 1e-9:
            best = (ll, l2, b, w_)
    val_ll, l2, b, w = best
    status = "calibrated_real" if data_kind == "real" else "calibrated_synthetic"
    weights = FusionWeights(bias=float(b), semantic=float(w[0]), geospatial=float(w[1]),
                            temporal=float(w[2]), category=float(w[3]), status=status,
                            semantic_trained_on="embedding" if semantic_mode in ("provider", "local") else "lexical")
    sc_va = np.array([weights.score(*x) for x in X_va])
    policy = load_fusion_policy()
    grid = np.linspace(0.05, 0.95, 91)
    best_f1 = max((prf(sc_va, y_va, t) for t in grid), key=lambda m: m["f1"])
    metrics = {
        "n_train_gated": int(len(y_tr)), "n_val_gated": int(len(y_va)), "val_positive_rate": round(float(y_va.mean()), 4),
        "val_auc_roc": round(auc_roc(sc_va, y_va), 4),
        "val_at_policy_duplicate_threshold": prf(sc_va, y_va, policy["thresholds"]["possible_duplicate"]),
        "val_best_f1_threshold": best_f1,
        "brier": round(float(np.mean((sc_va - y_va) ** 2)), 4),
        "val_logloss": round(val_ll, 4), "l2": l2,
        "semantic_weight_note": ("semantic weight is ~0: the lexical signal is not informative on synthetic pairs "
                                 "(duplicates use different phrasings). Fit with --semantic-mode provider for embeddings."
                                 if semantic_mode == "lexical" and w[0] < 0.05 else None),
    }
    ref = (data_dir / "DATASET_MANIFEST.json") if data_dir else (train_pairs if train_pairs else None)
    version = version or f"0.1.0+{(sha256_file(ref) if ref and ref.exists() else 'unknown')[:8]}"
    out = out_root / version
    out.mkdir(parents=True, exist_ok=True)
    doc = {
        "schema": WEIGHTS_SCHEMA, "version": version, "status": status,
        "semantic_trained_on": weights.semantic_trained_on, "synthetic_data": data_kind != "real",
        "trained_on": _trained_on(tr, data_kind),
        "bias": round(weights.bias, 6), "semantic": round(weights.semantic, 6), "geospatial": round(weights.geospatial, 6),
        "temporal": round(weights.temporal, 6), "category": round(weights.category, 6),
        "features": ["semantic", "geospatial", "temporal", "category"],
        "fusion_policy_version": policy["policy_version"], "metrics": metrics,
        "limitations": ([
            "Fitted on REAL agency-linked duplicate pairs from a single city; labels are agency-assigned, negatives are sampled (possible label noise).",
            "No narrative text exists in the source, so the semantic weight is not informative; fusion in production still needs embeddings.",
            "Do not publish or redistribute outputs unless the source licence is verified (see trained_on.sources[*].license_verified).",
        ] if data_kind == "real" else [
            "Fitted on SYNTHETIC pairs whose duplicate/non-duplicate construction encodes our own assumptions.",
        ]) + [
            "Weights are constrained non-negative (each signal is monotone); L2 strength chosen by validation log-loss.",
            "Lexical semantic signal is mono-lingual: cross-language duplicates need embeddings (re-fit with --semantic-mode provider).",
            "Thresholds in fusion_policy.v1.json are not tuned on real data unless status is calibrated_real; treat scores as ranking aids requiring human confirmation.",
        ],
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git_sha": git_sha(), "runtime": runtime_info(),
    }
    (out / "fusion_weights.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    (out / "MODEL_CARD.md").write_text(
        f"# Fusion calibrator {version}\n\n> " + ("REAL-DATA calibration (single source; see trained_on)." if data_kind == "real" else "SYNTHETIC-DATA calibration; not a real-world accuracy claim.") + "\n\n"
        f"- Weights: bias {doc['bias']}, semantic {doc['semantic']}, geospatial {doc['geospatial']}, temporal {doc['temporal']}, category {doc['category']}\n"
        f"- Semantic signal fitted on: **{doc['semantic_trained_on']}**\n- Validation metrics: `{json.dumps(metrics)}`\n\n"
        "## Limitations\n" + "\n".join(f"- {x}" for x in doc["limitations"]) + "\n", encoding="utf-8")
    print(f"fusion weights: {out / 'fusion_weights.json'}")
    print(json.dumps(metrics, indent=2))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=None, help="synthetic dataset dir (not needed with --kind real)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--kind", choices=["synthetic", "real"], default="synthetic")
    ap.add_argument("--pairs-train", type=Path); ap.add_argument("--pairs-val", type=Path)
    ap.add_argument("--semantic-mode", choices=["lexical", "provider", "local"], default="lexical")
    ap.add_argument("--embed-onnx", type=Path, default=None, help="exported M7 embedder directory (for --semantic-mode local)")
    ap.add_argument("--version", default=None)
    a = ap.parse_args(argv)
    if a.kind == "synthetic" and a.data is None:
        raise SystemExit("--data is required for --kind synthetic")
    run(a.data, a.out, semantic_mode=a.semantic_mode, version=a.version, train_pairs=a.pairs_train, val_pairs=a.pairs_val, data_kind=a.kind, embed_onnx=a.embed_onnx)
    return 0


if __name__ == "__main__":
    sys.exit(main())
