"""Build the tiny, deterministic B0 fixture artifact used by inference tests and smoke runs.

    python -m ai.training.src.make_fixture_artifact

Trains on a very small in-memory synthetic sample (no files needed) and writes
``ai/artifacts/fixtures/b0_tiny/`` (~100 KB, tracked in git). It is NOT a quality
model; it exists so the loader/service can be tested without Kaggle artifacts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ai.inference.config import load_taxonomy
from ai.inference.local.text_classifier import LocalTextClassifier
from ai.training.src.artifact_writer import write_classifier_artifact
from ai.training.src.synthetic import generator as gen
from ai.training.src.train_text_classifier import train

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "artifacts" / "fixtures" / "b0_tiny"
GOLDEN_TEXTS = [
    "there is a big pothole in the road near the school",
    "paani ki pipe leak ho rahi hai aur road par paani beh raha hai",
    "रस्त्यावर मोठा खड्डा पडला आहे",
    "the garbage bin is overflowing onto the street",
    "street light band hai aur road par andhera hai",
    "",  # empty -> abstain path
    "zzzz qqqq xxxx",  # no known n-grams
]


def build_fixture(out_dir: Path = DEFAULT_OUT) -> Path:
    tr = gen.generate_intake_split("train", 2, seed=7)
    va = gen.generate_intake_split("val", 1, seed=7)
    res = train(tr, va, c_grid=(3.0,), min_df=3, max_features=1000, seed=7, refit_on_trainval=False)
    write_classifier_artifact(
        out_dir, model_name="civic_text_b0_fixture", version="fixture-1", taxonomy=load_taxonomy(),
        label_ids=res["labels"], vectorizer=res["vectorizer"], coef=res["clf"].coef_, intercept=res["clf"].intercept_,
        temperature=res["temperature"],
        training={"seed": 7, "dataset_manifest_sha256": "in-memory-fixture", "n_train": len(tr), "n_val": len(va),
                  "hyperparameters": res["hyperparameters"], "split": "fixture only"},
        metrics={"note": "fixture artifact for tests; not a quality model", **res["metrics"]})
    clf = LocalTextClassifier.load(out_dir)
    golden = []
    for t in GOLDEN_TEXTS:
        p = clf.predict(t)
        golden.append({"text": t, "label_id": p.label_id, "abstained": p.abstained,
                       "subcategory_probability": round(p.subcategory_probability, 4)})
    (out_dir / "golden.json").write_text(json.dumps(golden, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_dir


if __name__ == "__main__":
    print(build_fixture())
    sys.exit(0)
