"""B1 (optional experiment): frozen multilingual sentence encoder + logistic-regression head.

    python -m ai.training.src.train_encoder_head \
        --data ai/artifacts/datasets/synthetic_v1 --out ai/artifacts/b1_experiments \
        --encoder intfloat/multilingual-e5-small --prefix "query: "

Requires ``sentence-transformers`` + ``torch`` and (on first run) internet access to
download the encoder, e.g. a Kaggle GPU notebook with Internet ON. NOT executed in
the repository's CI/sandbox. It reports metrics for comparison with B0 on the same
held-out split; there is deliberately NO production loader for B1 yet — if B1 wins
clearly, an ONNX export + inference loader is a follow-up decision (see README).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

from ai.inference.config import load_taxonomy
from ai.training.src.io_utils import git_sha, read_jsonl, runtime_info
from ai.training.src.train_text_classifier import macro_f1

EmbedFn = Callable[[Sequence[str]], np.ndarray]


def evaluate_embedding_classifier(embed_fn: EmbedFn, train_rows: list[dict], val_rows: list[dict],
                                  test_rows: list[dict], c_grid=(0.3, 1.0, 3.0, 10.0, 30.0), seed: int = 42) -> dict:
    """Pure function (encoder injected) so it is unit-testable without torch."""
    from sklearn.linear_model import LogisticRegression

    labels = load_taxonomy().label_ids
    idx = {l: i for i, l in enumerate(labels)}
    splits = {"train": train_rows, "val": val_rows, "test": test_rows}
    y = {n: np.array([idx[f"{r['category']}/{r['subcategory']}"] for r in rows]) for n, rows in splits.items()}
    X = {n: np.asarray(embed_fn([r["text"] for r in rows]), dtype=np.float32) for n, rows in splits.items()}
    best = None
    sweep = {}
    for C in c_grid:
        clf = LogisticRegression(C=C, max_iter=3000, random_state=seed).fit(X["train"], y["train"])
        f1 = macro_f1(y["val"], clf.predict(X["val"]), len(labels))
        sweep[str(C)] = round(f1, 4)
        if best is None or f1 > best[0] + 1e-9:
            best = (f1, C, clf)
    f1, C, clf = best
    out: dict = {"selected_C": C, "c_sweep_val_macro_f1": sweep, "embedding_dim": int(X["train"].shape[1])}
    for split in ("val", "test"):
        pred = clf.predict(X[split])
        out[f"{split}_subcategory_accuracy"] = round(float((pred == y[split]).mean()), 4)
        out[f"{split}_macro_f1"] = round(macro_f1(y[split], pred, len(labels)), 4)
        out[f"{split}_category_accuracy"] = round(float(np.mean(
            [labels[p].split("/")[0] == labels[t].split("/")[0] for p, t in zip(pred, y[split])])), 4)
    by_lang: dict[str, list[bool]] = {}
    for r, p, t in zip(test_rows, clf.predict(X["test"]), y["test"]):
        by_lang.setdefault(r["language"], []).append(bool(p == t))
    out["test_subcategory_accuracy_by_language"] = {k: round(float(np.mean(v)), 4) for k, v in sorted(by_lang.items())}
    return out


def load_sentence_encoder(name: str, prefix: str = "", device: str | None = None, batch_size: int = 64) -> EmbedFn:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:  # pragma: no cover - environment dependent
        raise SystemExit("sentence-transformers is not installed. On Kaggle: pip install -q sentence-transformers") from e
    model = SentenceTransformer(name, device=device)

    def embed(texts: Sequence[str]) -> np.ndarray:
        return model.encode([prefix + t for t in texts], batch_size=batch_size, normalize_embeddings=True,
                            show_progress_bar=False)
    return embed


def run(data_dir: Path, out_root: Path, encoder: str, prefix: str = "", embed_fn: EmbedFn | None = None) -> Path:
    tr, va, te = (read_jsonl(data_dir / f"{s}.jsonl") for s in ("train", "val", "test"))
    embed_fn = embed_fn or load_sentence_encoder(encoder, prefix)
    res = evaluate_embedding_classifier(embed_fn, tr, va, te)
    slug = encoder.replace("/", "__")
    out = out_root / slug
    out.mkdir(parents=True, exist_ok=True)
    report = {"experiment": "B1_encoder_plus_logreg", "encoder": encoder, "prefix": prefix, "synthetic_data": True,
              "split": "by template family and place pool", "results": res,
              "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git_sha": git_sha(),
              "runtime": runtime_info(),
              "note": "Compare with ai/evaluation/reports/intake_b0_local.json (same held-out test set). Synthetic data only."}
    (out / "b1_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(res, indent=2))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--encoder", default="intfloat/multilingual-e5-small")
    ap.add_argument("--prefix", default="query: ")
    a = ap.parse_args(argv)
    run(a.data, a.out, a.encoder, a.prefix)
    return 0


if __name__ == "__main__":
    sys.exit(main())
