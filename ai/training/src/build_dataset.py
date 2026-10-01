"""Build the SYNTHETIC multilingual civic dataset (train/val/test + duplicate pairs).

    python -m ai.training.src.build_dataset --out ai/artifacts/datasets/synthetic_v1 \
        [--eval-out ai/evaluation/datasets] [--seed 42] [--test-fold 4]

Splits are by template family AND place pool (see synthetic/generator.py).
The default fold/seed regenerates the committed evaluation set byte-for-byte on
the same Python minor version; ``--check-manifest`` reports any drift.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from ai.training.src.io_utils import git_sha, runtime_info, sha256_file, write_jsonl
from ai.training.src.synthetic import generator as gen

DISCLAIMER = ("SYNTHETIC DATA. Generated from hand-written templates for model development and regression "
              "testing. Not real citizen reports. Metrics measured on it do not estimate real-world accuracy. "
              "Hindi/Marathi text requires native-speaker review.")
DEFAULTS = dict(seed=42, test_fold=4, n_train=10, n_val=6, n_test=2, pairs_train=4000, pairs_val=1000, pairs_test=300)


def build(out: Path, *, seed: int, test_fold: int, n_train: int, n_val: int, n_test: int,
          pairs_train: int, pairs_val: int, pairs_test: int) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    files: dict[str, dict] = {}
    spec = [("train", n_train, pairs_train), ("val", n_val, pairs_val), ("test", n_test, pairs_test)]
    for split, n_fam, n_pairs in spec:
        rows = gen.generate_intake_split(split, n_fam, seed, test_fold)
        pairs = gen.generate_pairs(split, n_pairs, seed, test_fold)
        for name, data in ((f"{split}.jsonl", rows), (f"pairs_{split}.jsonl", pairs)):
            write_jsonl(out / name, data)
            files[name] = {"rows": len(data), "sha256": sha256_file(out / name)}
    manifest = {
        "dataset": "civicconnect-synthetic-civic-reports",
        "version": "1.0.0",
        "synthetic": True,
        "disclaimer": DISCLAIMER,
        "generator_version": gen.GENERATOR_VERSION,
        "params": {"seed": seed, "test_fold": test_fold, "n_per_family": {"train": n_train, "val": n_val, "test": n_test},
                   "pairs": {"train": pairs_train, "val": pairs_val, "test": pairs_test}},
        "split_design": {
            "unit": "template family (core phrase) and place pool",
            "family_indices": {s: gen.family_indices(s, test_fold) for s in ("train", "val", "test")},
            "place_indices": {s: [i for i, _ in gen.places_for(s, test_fold)] for s in ("train", "val", "test")},
            "leakage_note": ("Core issue phrases and place names are disjoint across splits. Frames, prefixes, suffixes "
                             "and noise processes are shared, as are the languages and the label taxonomy."),
        },
        "languages": ["en", "hi", "mr", "hi-Latn"],
        "files": files,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": git_sha(),
        "runtime": runtime_info(),
    }
    (out / "DATASET_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def check_against(manifest: dict, reference_path: Path) -> list[str]:
    """Return a list of drift messages (empty = reproduced identically)."""
    ref = json.loads(reference_path.read_text(encoding="utf-8"))
    problems = []
    for name, info in ref["files"].items():
        got = manifest["files"].get(name)
        if got is None or got["sha256"] != info["sha256"]:
            problems.append(f"{name}: sha256 differs from reference manifest")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--eval-out", type=Path, default=None, help="also publish test split as the tracked eval set")
    ap.add_argument("--check-manifest", type=Path, default=None, help="reference DATASET_MANIFEST.json to compare")
    for k, v in DEFAULTS.items():
        ap.add_argument(f"--{k.replace('_', '-')}", type=int, default=v)
    a = ap.parse_args(argv)
    params = {k: getattr(a, k) for k in DEFAULTS}
    m = build(a.out, **params)
    print(f"built dataset in {a.out}: " + ", ".join(f"{n}={i['rows']}" for n, i in m["files"].items()))
    rc = 0
    if a.check_manifest and a.check_manifest.exists():
        problems = check_against(m, a.check_manifest)
        if problems:
            print("WARNING: dataset differs from reference manifest (different Python minor version?):", *problems, sep="\n  ")
            rc = 0  # informational: reproducibility drift is reported, not fatal
        else:
            print("OK: dataset reproduced identically to reference manifest")
    if a.eval_out:
        a.eval_out.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(a.out / "test.jsonl", a.eval_out / "intake_eval.v1.jsonl")
        shutil.copyfile(a.out / "pairs_test.jsonl", a.eval_out / "fusion_eval_pairs.v1.jsonl")
        (a.eval_out / "manifest.v1.json").write_text((a.out / "DATASET_MANIFEST.json").read_text(encoding="utf-8"), encoding="utf-8")
        print(f"published eval set to {a.eval_out}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
