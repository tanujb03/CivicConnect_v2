"""Build (or verify) the seeded SYNTHETIC demo city of system design §58.

    python -m ai.training.src.build_demo_city --out ai/evaluation/datasets/demo_city_v1
    python -m ai.training.src.build_demo_city --out ai/evaluation/datasets/demo_city_v1 --check   # regenerate in memory and compare sha256

Outputs JSONL per entity (design §34 names), ``ground_truth.json`` (planted duplicates / recurring sites / hotspots / incidents) and ``manifest.json``
(seed, counts, sha256 of every file, recovery of the ground truth by the deterministic reference analytics). Everything is labelled synthetic.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from ai.inference.config import load_taxonomy

from .synthetic.city import CITY_VERSION, NOW, build_city
from .synthetic.city_checks import COLLECTIONS, MINIMUMS, counts, recovery, validate_city

DEFAULT_SEED, DEFAULT_CASES = 20261001, 560
NOTICE = ("SYNTHETIC DEMO DATA (system design §58). Every record is fictional and labelled synthetic; wards, users, cases, reports, incidents and all numbers are invented to "
          "make Admin/Overlooker dashboards, fusion, triage and analytics demonstrable. Nothing here describes a real city, citizen or municipal performance. "
          "Hindi/Marathi/Hinglish text comes from the project's template generator and has not been reviewed by native speakers.")


def _dump(rows: list[dict]) -> bytes:
    return ("\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in rows) + "\n").encode("utf-8")


def render_files(data: dict) -> dict[str, bytes]:
    files = {f"{k}.jsonl": _dump(data[k]) for k in COLLECTIONS}
    files["ground_truth.json"] = (json.dumps(data["ground_truth"], ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    return files


def manifest_for(data: dict, files: dict[str, bytes], seed: int, n_cases: int) -> dict:
    c = counts(data)
    return {"dataset": "demo_city", "version": "1.0.0", "synthetic": True, "notice": NOTICE, "generator_version": CITY_VERSION, "seed": seed, "requested_cases": n_cases,
            "anchor_now": NOW.isoformat(), "window_days": 240, "taxonomy_version": load_taxonomy().version, "design_section": "§58 Demo Dataset",
            "files": {n: {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(), **({"rows": b.count(b"\n")} if n.endswith(".jsonl") else {})} for n, b in sorted(files.items())},
            "counts": c, "minimums_required": MINIMUMS, "ground_truth_recovery_by_reference_analytics": recovery(data),
            "limitations": ["Priority/SLA come from the deterministic §36 rules in ai.inference, not a model.", "Lifecycle durations, reopen rates and backlog are invented.",
                            "Reports use template-family text: B0-style classifiers evaluated on it are only held-out for rows with text_split_pool == 'test'.",
                            "No images/audio are included: AI-4 before/after evidence is NOT represented."]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--cases", type=int, default=DEFAULT_CASES)
    ap.add_argument("--check", action="store_true", help="regenerate and compare with the files in --out (exit 1 on any difference)")
    a = ap.parse_args(argv)
    data = build_city(a.seed, a.cases)
    problems = validate_city(data)
    if problems:
        print("INVALID city:", *problems[:10], sep="\n  ", file=sys.stderr)
        return 1
    files = render_files(data)
    manifest = manifest_for(data, files, a.seed, a.cases)
    files["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    if a.check:
        bad = [n for n, b in files.items() if not (a.out / n).is_file() or (a.out / n).read_bytes() != b]
        if bad:
            print("DIFFERS from regenerated data:", bad, file=sys.stderr)
            return 1
        print("demo city matches its generator (seed", a.seed, ")")
        return 0
    a.out.mkdir(parents=True, exist_ok=True)
    for n, b in files.items():
        (a.out / n).write_bytes(b)
    c = manifest["counts"]
    print(f"wrote {len(files)} files to {a.out}: {c['cases']} cases, {c['report_signals']} reports, {c['wards']} wards, {c['departments']} departments, "
          f"{c['incidents']} incidents ({c['active_incidents']} active); recovery {manifest['ground_truth_recovery_by_reference_analytics']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
