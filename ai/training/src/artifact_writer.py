"""Write a ``civic-text-classifier/1`` artifact consumed by ``ai.inference``."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ai.inference.config import Taxonomy
from ai.inference.local.featurizer import NORMALIZER_VERSION, CharNgramVectorizer
from ai.inference.local.text_classifier import ARTIFACT_SCHEMA
from ai.training.src.io_utils import git_sha, runtime_info, sha256_file

LIMITATIONS = [
    "Trained and evaluated on SYNTHETIC template-generated reports only; metrics do not estimate real-world accuracy.",
    "Char n-gram model: no cross-lingual transfer; paraphrases that share no characters with training phrases may fail.",
    "Hindi/Marathi/Hinglish phrasing is hand-written and unreviewed by native speakers.",
    "Calibration (temperature) was fitted on synthetic validation data; probabilities are optimistic for real text.",
    "Not suitable as the sole basis for any workflow decision; proposals always require human confirmation.",
]


def write_classifier_artifact(out_dir: Path, *, model_name: str, version: str, taxonomy: Taxonomy,
                              label_ids: list[str], vectorizer: CharNgramVectorizer, coef: np.ndarray,
                              intercept: np.ndarray, temperature: float, training: dict, metrics: dict) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    coef32, icpt32 = coef.astype(np.float32), intercept.astype(np.float32)
    # vocab ordered by index for readable, stable diffs
    vocab_sorted = dict(sorted(vectorizer.vocab.items(), key=lambda kv: kv[1]))
    (out_dir / "vocab.json").write_text(json.dumps(vocab_sorted, ensure_ascii=False), encoding="utf-8")
    np.savez(out_dir / "weights.npz", coef=coef32, intercept=icpt32, idf=vectorizer.idf.astype(np.float32))
    content_hash = hashlib.sha256(coef32.tobytes() + icpt32.tobytes() + vectorizer.idf.astype(np.float32).tobytes()).hexdigest()
    manifest = {
        "artifact_schema": ARTIFACT_SCHEMA,
        "model_name": model_name,
        "model_version": version,
        "kind": "tfidf_char_ngram_logreg",
        "synthetic_data": True,
        "label_ids": label_ids,
        "taxonomy_version": taxonomy.version,
        "taxonomy_status": taxonomy.status,
        "vectorizer": {"analyzer": "char_wb", "ngram_range": list(vectorizer.ngram_range),
                       "sublinear_tf": vectorizer.sublinear_tf, "normalizer": NORMALIZER_VERSION,
                       "n_features": vectorizer.n_features},
        "calibration": {"method": "temperature", "temperature": round(float(temperature), 4),
                        "fitted_on": "synthetic validation split (unseen template families)"},
        "files": {"weights.npz": sha256_file(out_dir / "weights.npz"), "vocab.json": sha256_file(out_dir / "vocab.json")},
        "weights_content_sha256": content_hash,
        "training": training,
        "metrics": metrics,
        "limitations": LIMITATIONS,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": git_sha(),
        "runtime": runtime_info(),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "MODEL_CARD.md").write_text(model_card(manifest), encoding="utf-8")
    return manifest


def model_card(m: dict) -> str:
    met = m.get("metrics", {})
    lines = [
        f"# Model card — {m['model_name']} {m['model_version']}", "",
        "> **SYNTHETIC-DATA MODEL.** Trained only on template-generated reports. Do not quote its metrics as real-world accuracy.", "",
        "## What it is",
        f"- Kind: `{m['kind']}` (character n-gram TF-IDF + multinomial logistic regression, numpy inference)",
        f"- Labels: {len(m['label_ids'])} subcategories (`category/subcategory`), taxonomy `{m['taxonomy_version']}` ({m.get('taxonomy_status')})",
        f"- Vectoriser: `{m['vectorizer']['analyzer']}` n-grams {m['vectorizer']['ngram_range']}, {m['vectorizer']['n_features']} features, normaliser `{m['vectorizer']['normalizer']}`",
        f"- Calibration: temperature scaling, T={m['calibration']['temperature']}",
        "- Intended use: offline/unavailable-provider **fallback** for AI-1 intake, cross-check of the provider answer, evaluation baseline.",
        "- Not intended for: autonomous decisions, severity/priority, any real-world accuracy claim.", "",
        "## Training",
        f"- Dataset: {m['training'].get('dataset_manifest_sha256', 'n/a')[:16]}… (see DATASET_MANIFEST.json); seed {m['training'].get('seed')}",
        f"- Hyperparameters: {json.dumps(m['training'].get('hyperparameters', {}))}",
        f"- Git SHA: `{m.get('git_sha')}`; created {m['created_at']}; runtime {json.dumps(m['runtime'])}", "",
        "## Metrics (synthetic validation split; unseen template families)",
    ]
    for k, v in met.items():
        lines.append(f"- {k}: {v}")
    lines += ["", "Held-out *test* metrics are produced by `ai/evaluation/run_eval.py` and stored in the evaluation report.", "",
              "## Limitations"] + [f"- {x}" for x in m["limitations"]] + [""]
    return "\n".join(lines)
