"""Build (or verify) the SYNTHETIC AI-4 scenario set from the committed demo city.

    python -m ai.training.src.build_resolution_scenarios --out ai/evaluation/datasets/resolution_v1
    python -m ai.training.src.build_resolution_scenarios --out ai/evaluation/datasets/resolution_v1 --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from .synthetic.resolution import ARCHETYPES, DEFAULT_SEED, RESOLUTION_VERSION, build_scenarios

CITY = Path(__file__).resolve().parents[2] / "evaluation" / "datasets" / "demo_city_v1"
NOTICE = ("SYNTHETIC. Planted AI-4 scenarios overlaid on the synthetic demo city. They contain NO images: photo presence is a flag, and real before/after resolution "
          "evidence does not exist anywhere in this project. Ground truth (`truly_unresolved`, `detectable_by`) is invented by construction. Hindi/Marathi notes are unreviewed.")


def _read(name: str) -> list[dict]:
    return [json.loads(x) for x in (CITY / name).read_text(encoding="utf-8").splitlines() if x.strip()]


def render(seed: int, n: int) -> dict[str, bytes]:
    signals = {s["case_id"]: s for s in _read("report_signals.jsonl") if s.get("is_primary")}
    rows = build_scenarios(_read("cases.jsonl"), _read("work_orders.jsonl"), signals, seed=seed, n=n)
    body = ("\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in rows) + "\n").encode("utf-8")
    manifest = {"dataset": "resolution_scenarios", "version": RESOLUTION_VERSION, "synthetic": True, "notice": NOTICE, "seed": seed, "requested": n,
                "derived_from": "demo_city_v1", "rows": len(rows), "archetypes": dict(sorted(Counter(r["archetype"] for r in rows).items())),
                "archetype_spec": [{"archetype": a[0], "weight": a[1], "truly_unresolved": a[2], "detectable_by": a[6]} for a in ARCHETYPES],
                "truly_unresolved": sum(r["truly_unresolved"] for r in rows), "scenarios_sha256": hashlib.sha256(body).hexdigest()}
    return {"scenarios.jsonl": body, "manifest.json": (json.dumps(manifest, ensure_ascii=False, indent=1) + "\n").encode("utf-8")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--n", type=int, default=240)
    ap.add_argument("--check", action="store_true", help="regenerate in memory and compare with --out")
    a = ap.parse_args(argv)
    files = render(a.seed, a.n)
    if a.check:
        bad = [k for k, v in files.items() if not (a.out / k).exists() or (a.out / k).read_bytes() != v]
        print("reproducible" if not bad else f"DIFFERS: {bad}")
        return 1 if bad else 0
    a.out.mkdir(parents=True, exist_ok=True)
    for k, v in files.items():
        (a.out / k).write_bytes(v)
    print(f"wrote {len(files)} files to {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
