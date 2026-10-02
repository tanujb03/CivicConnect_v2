"""End-to-end evaluation of the AI capabilities on the SYNTHETIC demo city (§58 data, §57 metrics).

    python -m ai.evaluation.eval_demo_city --artifact ai/artifacts/civic_text_b0/<version> [--fusion-weights <dir>]

What is measured (all SYNTHETIC; none of it is real-world accuracy):
  AI-1 intake    category/subcategory accuracy of the local B0 classifier on the demo reports, split into HELD-OUT template families
                 (``text_split_pool == test``: the only slice that is not in-distribution for the training data) and the rest
  AI-2 fusion    precision/recall on planted duplicate pairs vs planted near-but-distinct and sampled negatives
  AI-3 triage    stability of the deterministic §36 rules (recomputed priority/SLA equals the stored value) — a consistency check, not accuracy
  AI-5 analytics recovery of the planted recurring sites and hotspots by the deterministic reference analytics (the LLM never finds hotspots)
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from ai.evaluation import eval_fusion, eval_intake
from ai.evaluation.analytics_reference import haversine_m
from ai.evaluation.provenance import build_provenance, claims_for, validate_track
from ai.evaluation.run_eval import HERE, write_report
from ai.inference.config import load_taxonomy
from ai.inference.fusion.scoring import FusionWeights
from ai.inference.intake.service import IntakeService
from ai.inference.local.text_classifier import LocalTextClassifier
from ai.inference.schemas import TriageRequest
from ai.inference.triage.service import TriageService

DEFAULT_DIR = HERE / "datasets" / "demo_city_v1"
COLLECTIONS = ("wards", "departments", "users", "cases", "report_signals", "case_relations", "status_events", "work_orders", "verifications", "incidents")


def load_city(path: Path = DEFAULT_DIR) -> dict:
    d = {k: [json.loads(ln) for ln in (path / f"{k}.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()] for k in COLLECTIONS}
    d["ground_truth"] = json.loads((path / "ground_truth.json").read_text(encoding="utf-8"))
    return d


def intake_rows(d: dict) -> list[dict]:
    cases = {c["id"]: c for c in d["cases"]}
    rows = []
    for s in d["report_signals"]:
        c = cases[s["case_id"]]
        rows.append({"id": s["id"], "text": s["original_text"], "category": c["category"], "subcategory": c["subcategory"], "department": c["department_id"], "gold_severity": None,
                     "language": s["original_language"], "code_mixed": s["code_mixed"], "noisy": False, "family_id": s["family_id"], "split": s["text_split_pool"], "synthetic": True})
    return rows


def fusion_pairs(d: dict, seed: int = 7) -> list[dict]:
    cases = {c["id"]: c for c in d["cases"]}
    sigs = {s["id"]: s for s in d["report_signals"]}
    primary = {c["id"]: sigs[c["primary_signal_id"]] for c in d["cases"]}

    def side(case_id: str, sig: dict | None = None) -> dict:
        c, s = cases[case_id], sig or primary[case_id]
        return {"case_id": s["id"] if sig else case_id, "text": s["original_text"], "language": s["original_language"], "category": c["category"], "subcategory": c["subcategory"],
                "latitude": s["latitude"], "longitude": s["longitude"], "created_at": s["created_at"].replace("Z", "+00:00")}

    def pair(i: int, kind: str, label: int, a: dict, b: dict) -> dict:
        return {"pair_id": f"city-{i:04d}", "pair_type": kind, "label": label, "cross_language": a["language"] != b["language"], "a": a, "b": b, "synthetic": True}
    out: list[dict] = []
    for g in d["ground_truth"]["duplicate_groups_merged"]:
        first = sigs[g["signal_ids"][0]]
        for sid in g["signal_ids"][1:]:
            out.append(pair(len(out), "duplicate_report_same_case", 1, side(g["case_id"], first), side(g["case_id"], sigs[sid])))
    for p in d["ground_truth"]["possible_duplicate_pairs"]:
        out.append(pair(len(out), "duplicate_separate_cases", 1, side(p["case_a"]), side(p["case_b"])))
    for p in d["ground_truth"]["near_distinct_pairs"]:
        out.append(pair(len(out), "distinct_near", 0, side(p["case_a"]), side(p["case_b"])))
    rng = random.Random(seed)
    ids = [c["id"] for c in d["cases"]]
    n_pos = sum(p["label"] for p in out)
    tries = 0
    while sum(p["pair_type"] in ("distinct_far", "distinct_other_category") for p in out) < 2 * n_pos and tries < 20000:
        tries += 1
        a, b = rng.sample(ids, 2)
        ca, cb = cases[a], cases[b]
        dist = haversine_m((ca["location"]["latitude"], ca["location"]["longitude"]), (cb["location"]["latitude"], cb["location"]["longitude"]))
        if dist > 400 and ca["subcategory"] == cb["subcategory"]:
            out.append(pair(len(out), "distinct_far", 0, side(a), side(b)))
        elif dist < 120 and ca["category"] != cb["category"]:
            out.append(pair(len(out), "distinct_other_category", 0, side(a), side(b)))
    return out


def evaluate_triage_stability(d: dict) -> dict:
    t = load_taxonomy()
    svc = TriageService(None, t)
    n = bad = 0
    for c in d["cases"]:
        r = svc.analyze(TriageRequest(category=c["category"], subcategory=c["subcategory"], support_count=c["support_count"], case_age_hours=0, recurrence_count=c["recurrence_count"],
                                      location_tags=c["location_tags"], incident_active=c["incident_id"] is not None)).recommendation
        n += 1
        bad += (r.priority, r.sla_hours, r.severity) != (c["priority"], c["sla_hours"], c["severity"])
    return {"task": "triage_rules_stability", "n": n, "mismatches": bad, "note": "Deterministic §36 rules re-applied to the stored inputs reproduce the stored priority/SLA/severity. A consistency check of "
                                                                              "the rules and the data, NOT model accuracy: AI never sets priority."}


def evaluate_city(d: dict, artifact: Path | None, fusion_weights: Path | None) -> dict:
    from ai.training.src.synthetic.city_checks import counts, recovery
    clf = LocalTextClassifier.load(artifact) if artifact else None
    out: dict = {"task": "demo_city", "dataset": {"counts": {k: v for k, v in counts(d).items() if k != "multilingual_signals"}, "languages": counts(d)["multilingual_signals"]}}
    if clf is not None:
        svc = IntakeService(provider=None, classifier=clf)
        rows = intake_rows(d)
        held = [r for r in rows if r["split"] == "test"]
        out["intake_heldout_families"] = {**eval_intake.evaluate(svc, held), "slice": "text_split_pool == test (template families unseen in B0 training)"}
        out["intake_all_reports_in_distribution_mixed"] = {**eval_intake.evaluate(svc, rows), "slice": "ALL demo reports; most template families were seen in training: optimistic, regression signal only"}
        out["classifier"] = f"{clf.model_name}@{clf.model_version}"
    else:
        out["intake"] = "SKIPPED: pass --artifact to evaluate the local classifier"
    w = FusionWeights.load(fusion_weights) if fusion_weights else None
    out["fusion"] = eval_fusion.evaluate(fusion_pairs(d), w)
    out["triage"] = evaluate_triage_stability(d)
    out["analytics_recovery"] = recovery(d)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--city", type=Path, default=DEFAULT_DIR)
    ap.add_argument("--artifact", type=Path, default=None, help="B0 classifier artifact directory")
    ap.add_argument("--fusion-weights", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=HERE / "reports")
    ap.add_argument("--name", default="demo_city_synthetic")
    a = ap.parse_args(argv)
    d = load_city(a.city)
    prov = build_provenance([{"synthetic": True}] * len(d["cases"]))
    validate_track("synthetic", prov)
    claims = claims_for("synthetic", prov)
    results = evaluate_city(d, a.artifact, a.fusion_weights)
    p = write_report(a.out, a.name, {"track": "synthetic", "task": "demo_city", "system": "local+rules", "artifact": results.get("classifier"), "datasets": {a.city.name: "demo_city_v1"},
                                     "taxonomy_version": load_taxonomy().version, "provenance": prov, "claims": claims, "results": results})
    print("report:", p, "\nbanner:", claims["banner"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
