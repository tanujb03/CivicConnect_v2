"""Calibrate the duplicate-search thresholds against the planted duplicates of the synthetic demo city, using the embeddings stored in ``case_embeddings``.

    python -m backend.scripts.calibrate_duplicates [--out docs/DUPLICATE_CALIBRATION.md] [--json-out path.json] [--samples 500] [--seed 7]

Run it AFTER ``python -m backend.scripts.backfill_embeddings`` on a database whose demo cases have embeddings. It writes no database row and sends nothing anywhere.

Design rule: the DETERMINISTIC GATE stays primary (same category, radius, time window from ``fusion_policy.v1.json`` ``candidate_generation``, exactly as ``repo.fusion_candidates``
applies it); embeddings only RANK candidates inside the gate. So everything is measured on pairs that PASS the gate, and the out-of-gate random pairs are shown only as the baseline
of what a bare cosine cutoff would face (unrelated English sentences were seen at cosine 0.69, a true Hindi/English match at 0.91: a bare cutoff is not enough).

Ground truth (``ai/evaluation/datasets/demo_city_v1/ground_truth.json``): positives = ``possible_duplicate_pairs`` (separate cases that are duplicates); hard negatives =
``near_distinct_pairs`` plus every OTHER pair of cases that passes the gate (these may hide unlabelled duplicates, which can only make precision look worse). The
``duplicate_groups_merged`` are several reports inside ONE case, so a case embedding cannot score them; they are counted and left out.

Chosen thresholds, by an explicit rule on the gate pairs: ``duplicate_threshold`` = the lowest cosine threshold (grid 0.50..0.98 step 0.02) with precision >= 0.90, ``related_threshold`` =
the lowest with precision >= 0.75; when none qualifies, the F1-maximising threshold and a WARNING. The same rule is applied to the fused score (the quantity the policy file's
thresholds apply to) to say whether those policy thresholds would change. The policy file is never edited here.

Refuses (exit 2, no file written) when fewer than 90% of the cases involved have an embedding. Every number comes from SYNTHETIC data: no real-world claim.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from sqlalchemy import select

from ai.evaluation.eval_demo_city import DEFAULT_DIR, load_city
from ai.inference.config import load_fusion_policy
from ai.inference.fusion.scoring import FusionWeights
from ai.inference.fusion.similarity import category_signal, geospatial_signal, haversine_m, temporal_signal
from backend.ai_gateway.vectors import cosine
from backend.db.session import session_scope
from backend.models import CaseEmbedding

THRESHOLDS = [round(0.50 + 0.02 * i, 2) for i in range(25)]          # 0.50 .. 0.98
DUPLICATE_PRECISION, RELATED_PRECISION = 0.90, 0.75
MIN_COVERAGE, MIN_POSITIVES, MIN_SUPPORT = 0.90, 30, 5
DEFAULT_OUT = Path("docs/DUPLICATE_CALIBRATION.md")
CAUTION = "SYNTHETIC demo data: no real-world claim. The thresholds below are a starting point to be re-checked on real reports."


class CoverageError(RuntimeError):
    """Too few of the involved cases have an embedding: no thresholds are produced."""


@dataclass(frozen=True)
class Case:
    id: str
    category: str
    subcategory: str | None
    lat: float
    lon: float
    at: datetime
    status: str | None


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------- pairs
def city_cases(city: Mapping[str, Any]) -> dict[str, Case]:
    out = {}
    for c in city["cases"]:
        loc = c["location"]
        out[c["id"]] = Case(c["id"], c["category"], c.get("subcategory"), loc["latitude"], loc["longitude"], datetime.fromisoformat(c["created_at"].replace("Z", "+00:00")), c.get("status"))
    return out


def gate(a: Case, b: Case, cg: Mapping[str, Any]) -> tuple[bool, float, float]:
    """(passes, distance in metres, age gap in hours): the same three bounds as ``FusionService.in_policy`` / ``repo.fusion_candidates``."""
    d = haversine_m(a.lat, a.lon, b.lat, b.lon)
    age_h = abs((a.at - b.at).total_seconds()) / 3600.0
    ok = d <= cg["radius_m"] and age_h <= 24 * cg["time_window_days"] and (not cg["same_category_required"] or a.category == b.category)
    return ok, d, age_h


def key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def build_pairs(city: Mapping[str, Any], cg: Mapping[str, Any], samples: int = 500, seed: int = 7) -> dict[str, Any]:
    """Pairs by class. ``positives`` / ``near_distinct`` / ``other_gated`` pass the gate; ``out_of_gate`` is a fixed-seed random sample of pairs that do NOT."""
    cases = city_cases(city)
    truth = city["ground_truth"]
    pos_all = {key(p["case_a"], p["case_b"]) for p in truth["possible_duplicate_pairs"] if p["case_a"] in cases and p["case_b"] in cases}
    near_all = {key(p["case_a"], p["case_b"]) for p in truth["near_distinct_pairs"] if p["case_a"] in cases and p["case_b"] in cases} - pos_all
    positives = {k for k in pos_all if gate(cases[k[0]], cases[k[1]], cg)[0]}
    near = {k for k in near_all if gate(cases[k[0]], cases[k[1]], cg)[0]}
    labelled = pos_all | near_all
    live = sorted(i for i, c in cases.items() if c.status != "REJECTED")
    other: set[tuple[str, str]] = set()
    groups: dict[Any, list[str]] = {}
    for i in live:
        groups.setdefault(cases[i].category if cg["same_category_required"] else None, []).append(i)
    for ids in groups.values():
        for x, a in enumerate(ids):
            for b in ids[x + 1:]:
                if (k := key(a, b)) not in labelled and gate(cases[a], cases[b], cg)[0]:
                    other.add(k)
    rng = random.Random(seed)
    outside: set[tuple[str, str]] = set()
    tries = 0
    while len(outside) < samples and tries < samples * 200 and len(live) > 1:
        tries += 1
        a, b = rng.sample(live, 2)
        if (k := key(a, b)) not in labelled and k not in outside and not gate(cases[a], cases[b], cg)[0]:
            outside.add(k)
    return {"cases": cases, "positives": sorted(positives), "near_distinct": sorted(near), "other_gated": sorted(other), "out_of_gate": sorted(outside),
            "positives_planted": len(pos_all), "near_distinct_planted": len(near_all),
            "merged_signal_pairs": sum(max(0, len(g["signal_ids"]) - 1) for g in truth.get("duplicate_groups_merged", []))}


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------- vectors
def load_vectors(case_ids: Sequence[str], session_factory: Callable[[], Any] = session_scope) -> dict[str, tuple[str, list[float]]]:
    """case id -> (embedding model, JSON vector) for the cases that have one."""
    out: dict[str, tuple[str, list[float]]] = {}
    ids = list(case_ids)
    with session_factory() as db:
        for i in range(0, len(ids), 500):
            for r in db.execute(select(CaseEmbedding).where(CaseEmbedding.case_id.in_(ids[i:i + 500]))).scalars():
                if r.vector:
                    out[r.case_id] = (r.embedding_model or r.model, [float(x) for x in r.vector])
    return out


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------- statistics
def percentile(xs: Sequence[float], q: float) -> float:
    """Linear-interpolated percentile of a sorted sequence."""
    k = (len(xs) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def dist_stats(values: Sequence[float]) -> dict[str, Any]:
    xs = sorted(values)
    if not xs:
        return {"n": 0, "min": None, "p10": None, "median": None, "p90": None, "max": None}
    return {"n": len(xs), "min": xs[0], "p10": percentile(xs, 0.10), "median": percentile(xs, 0.5), "p90": percentile(xs, 0.90), "max": xs[-1]}


def sweep(pos: Sequence[float], neg: Sequence[float], near: Sequence[float] = (), thresholds: Sequence[float] = THRESHOLDS, missing_pos: int = 0) -> list[dict[str, Any]]:
    """Per threshold t (predict duplicate when score >= t): tp / fp / fn, precision (None when nothing is predicted), recall, F1, and the precision against ``near`` alone.
    ``missing_pos`` planted positives without a comparable vector can never be predicted: they count as false negatives at every threshold."""
    rows = []
    for t in thresholds:
        tp, fp, fn = sum(s >= t for s in pos), sum(s >= t for s in neg), sum(s < t for s in pos) + missing_pos
        p = tp / (tp + fp) if tp + fp else None
        r = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * p * r / (p + r) if p and r else 0.0
        fp_near = sum(s >= t for s in near)
        rows.append({"threshold": t, "tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f1,
                     "precision_vs_near_distinct": tp / (tp + fp_near) if tp + fp_near else None})
    return rows


def lowest_with_precision(rows: Sequence[Mapping[str, Any]], minimum: float, min_tp: int = 1) -> Mapping[str, Any] | None:
    return next((r for r in rows if r["tp"] >= max(1, min_tp) and r["precision"] is not None and r["precision"] >= minimum), None)


def choose_thresholds(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The explicit rule: duplicate = lowest threshold with precision >= 0.90 AND at least 5 true positives (precision from fewer is noise), related = lowest with precision
    >= 0.75; the F1 maximum (higher threshold on a tie) and a WARNING otherwise. (True positives only fall as the threshold rises, so when the lowest precision-qualifying
    threshold lacks support no higher one has it: the rule then falls back and says so.)"""
    best = max(rows, key=lambda r: (r["f1"], r["threshold"]))
    warnings: list[str] = []
    notes: list[str] = []
    picked = {}
    for name, minimum, support in (("duplicate_threshold", DUPLICATE_PRECISION, MIN_SUPPORT), ("related_threshold", RELATED_PRECISION, 1)):
        row = lowest_with_precision(rows, minimum, support)
        first = lowest_with_precision(rows, minimum)
        extra = f" with at least {support} true positives" if support > 1 else ""
        rule = f"lowest threshold with precision >= {minimum:.2f}{extra}"
        if row is not None and first is not None and first["threshold"] != row["threshold"]:
            notes.append(f"{name}: {first['threshold']:.2f} reaches precision >= {minimum:.2f} with only {first['tp']} true positives (< {support}); moved to {row['threshold']:.2f}")
        if row is None:
            row, rule = best, f"F1-maximising threshold (no threshold reaches precision >= {minimum:.2f}{extra})"
            warnings.append(f"WARNING: {name}: no threshold on the grid reaches precision >= {minimum:.2f}{extra}; the F1-maximising threshold {best['threshold']:.2f} is shown instead")
            if first is not None:
                notes.append(f"{name}: {first['threshold']:.2f} reaches precision >= {minimum:.2f} with only {first['tp']} true positives (< {support}): too little support")
        picked[name] = {"value": row["threshold"], "rule": rule, "precision": row["precision"], "recall": row["recall"], "f1": row["f1"], "tp": row["tp"], "fp": row["fp"], "fn": row["fn"]}
    if picked["related_threshold"]["value"] > picked["duplicate_threshold"]["value"]:
        picked["related_threshold"] = {**picked["duplicate_threshold"], "rule": "capped at the duplicate threshold (the fallback gave a higher value)"}
        warnings.append("WARNING: related_threshold was capped at duplicate_threshold")
    return {**picked, "warnings": warnings, "notes": notes}


def compare_with_policy(rows: Sequence[Mapping[str, Any]], chosen: Mapping[str, Any], policy_th: Mapping[str, float]) -> dict[str, Any]:
    """The fused-score thresholds of the policy file against the same rule: precision / recall where the policy puts them, and whether they would move (> two grid steps)."""
    out: dict[str, Any] = {}
    for name, pol_key, chosen_key in (("duplicate", "possible_duplicate", "duplicate_threshold"), ("related", "related", "related_threshold")):
        at = min(rows, key=lambda r: abs(r["threshold"] - policy_th[pol_key]))
        diff = round(chosen[chosen_key]["value"] - policy_th[pol_key], 2)
        out[name] = {"policy": policy_th[pol_key], "chosen": chosen[chosen_key]["value"], "difference": diff, "would_change": abs(diff) > 0.04,
                     "policy_precision": at["precision"], "policy_recall": at["recall"], "policy_row_threshold": at["threshold"]}
    return out


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------- calibration
def calibrate(city: Mapping[str, Any], vectors: Mapping[str, tuple[str, list[float]]], policy: Mapping[str, Any], *, samples: int = 500, seed: int = 7,
              weights: FusionWeights | None = None, pairs: dict[str, Any] | None = None) -> dict[str, Any]:
    """The whole analysis as a JSON-able dict. ``CoverageError`` when fewer than 90% of the involved cases have an embedding."""
    cg = policy["candidate_generation"]
    pr = pairs or build_pairs(city, cg, samples, seed)
    cases: dict[str, Case] = pr["cases"]
    classes = {c: pr[c] for c in ("positives", "near_distinct", "other_gated", "out_of_gate")}
    involved = sorted({i for ps in classes.values() for p in ps for i in p})
    embedded = [i for i in involved if i in vectors]
    coverage = len(embedded) / len(involved) if involved else 0.0
    counts = {"cases": len(cases), "cases_embedded": sum(i in vectors for i in cases), "cases_missing_embedding": sum(i not in vectors for i in cases),
              "involved": len(involved), "involved_embedded": len(embedded), "coverage": coverage,
              "positives_planted": pr["positives_planted"], "positives_in_gate": len(classes["positives"]), "positives_out_of_gate": pr["positives_planted"] - len(classes["positives"]),
              "merged_signal_pairs_not_evaluable": pr["merged_signal_pairs"], "near_distinct_planted": pr["near_distinct_planted"], "near_distinct_in_gate": len(classes["near_distinct"]),
              "other_gated": len(classes["other_gated"]), "out_of_gate_sample": len(classes["out_of_gate"])}
    if not involved or coverage < MIN_COVERAGE:
        raise CoverageError(f"only {len(embedded)} of {len(involved)} involved cases ({coverage:.0%}) have an embedding (need {MIN_COVERAGE:.0%}); run backend.scripts.backfill_embeddings first. "
                            f"{counts['cases_missing_embedding']} of {counts['cases']} demo cases lack one")
    tally: dict[tuple[str, int], int] = {}
    for i in embedded:
        tally[(vectors[i][0], len(vectors[i][1]))] = tally.get((vectors[i][0], len(vectors[i][1])), 0) + 1
    model, dim = max(tally, key=lambda k: (tally[k], k))
    comparable = {i for i in embedded if (vectors[i][0], len(vectors[i][1])) == (model, dim)}
    pos_cases = {i for p in classes["positives"] for i in p}
    pos_cov = len(pos_cases & comparable) / len(pos_cases) if pos_cases else 0.0
    counts["positives_coverage"] = pos_cov
    if pos_cov < MIN_COVERAGE:
        raise CoverageError(f"only {len(pos_cases & comparable)} of {len(pos_cases)} cases of the planted duplicate pairs ({pos_cov:.0%}) have a comparable embedding (need {MIN_COVERAGE:.0%}); "
                            f"run backend.scripts.backfill_embeddings first")
    w = weights or FusionWeights.from_prior(policy)
    cos: dict[str, list[float]] = {c: [] for c in classes}
    fused: dict[str, list[float]] = {c: [] for c in classes}
    dropped = {c: 0 for c in classes}
    for c, ps in classes.items():
        for a, b in ps:
            if a not in comparable or b not in comparable:
                dropped[c] += 1
                continue
            s = cosine(vectors[a][1], vectors[b][1])
            _, d, age_h = gate(cases[a], cases[b], cg)
            cos[c].append(s)
            fused[c].append(w.score(s, geospatial_signal(d, cg["radius_m"]), temporal_signal(age_h, cg["time_window_days"]),
                                    category_signal(cases[a].category, cases[a].subcategory, cases[b].category, cases[b].subcategory)))
    counts.update(pairs_scored={c: len(cos[c]) for c in classes}, pairs_dropped_no_comparable_vector=dropped, model=model, dimension=dim, models_seen=sorted({m for m, _ in tally}))
    result: dict[str, Any] = {"caution": CAUTION, "gate": dict(cg), "policy_thresholds": dict(policy["thresholds"]), "seed": seed, "grid": THRESHOLDS, "counts": counts,
                              "notes": [], "refused": False}
    n_pos = len(cos["positives"])
    if n_pos == 0 or not (cos["near_distinct"] or cos["other_gated"]):
        raise CoverageError(f"cannot choose thresholds: {n_pos} scored positives and {len(cos['near_distinct']) + len(cos['other_gated'])} scored gate negatives")
    if n_pos < MIN_POSITIVES:
        result["notes"].append(f"CAUTION: only {n_pos} positive pairs (fewer than {MIN_POSITIVES}): the precision and the chosen thresholds are very uncertain. {CAUTION}")
    gate_neg = {"cosine": cos["near_distinct"] + cos["other_gated"], "fused": fused["near_distinct"] + fused["other_gated"]}
    result["cosine"] = {"distribution": {c: dist_stats(v) for c, v in cos.items()}}
    miss = dropped["positives"]
    counts["positives_counted_as_false_negatives"] = miss
    rows = sweep(cos["positives"], gate_neg["cosine"], cos["near_distinct"], missing_pos=miss)
    result["cosine"].update(sweep=rows, chosen=choose_thresholds(rows))
    frows = sweep(fused["positives"], gate_neg["fused"], fused["near_distinct"], missing_pos=miss)
    fchosen = choose_thresholds(frows)
    result["fused"] = {"weights_status": w.status, "distribution": {c: dist_stats(v) for c, v in fused.items()}, "sweep": frows, "chosen": fchosen,
                       "versus_policy": compare_with_policy(frows, fchosen, policy["thresholds"])}
    result["warnings"] = [*result["cosine"]["chosen"]["warnings"], *[f"fused: {x}" for x in fchosen["warnings"]]]
    result["notes"] += [*result["cosine"]["chosen"]["notes"], *[f"fused: {x}" for x in fchosen["notes"]]]
    if miss:
        result["notes"].append(f"{miss} planted positive pair(s) have no comparable vector and count as FALSE NEGATIVES in every recall figure")
    return result


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------- output
def _f(x: float | None, nd: int = 3) -> str:
    return "-" if x is None else f"{x:.{nd}f}"


def _kv(d: Mapping[str, Any]) -> str:
    return ", ".join(f"{k} {v}" for k, v in d.items())


def _dist_table(dist: Mapping[str, Mapping[str, Any]]) -> list[str]:
    names = {"positives": "planted duplicates (in gate)", "near_distinct": "near-distinct pairs (in gate)", "other_gated": "other pairs in the gate", "out_of_gate": "random pairs OUT of the gate (baseline)"}
    L = ["| class | n | min | p10 | median | p90 | max |", "|---|---:|---:|---:|---:|---:|---:|"]
    for k, label in names.items():
        s = dist[k]
        L.append(f"| {label} | {s['n']} | {_f(s['min'])} | {_f(s['p10'])} | {_f(s['median'])} | {_f(s['p90'])} | {_f(s['max'])} |")
    return L


def _sweep_table(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    L = ["| threshold | TP | FP | FN | precision | recall | F1 | precision vs near-distinct only |", "|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        L.append(f"| {r['threshold']:.2f} | {r['tp']} | {r['fp']} | {r['fn']} | {_f(r['precision'])} | {_f(r['recall'])} | {_f(r['f1'])} | {_f(r['precision_vs_near_distinct'])} |")
    return L


def _chosen_lines(chosen: Mapping[str, Any]) -> list[str]:
    L = []
    for name in ("duplicate_threshold", "related_threshold"):
        c = chosen[name]
        L.append(f"- `{name}` = **{c['value']:.2f}** ({c['rule']}): precision {_f(c['precision'])}, recall {_f(c['recall'])}, F1 {_f(c['f1'])} (TP {c['tp']}, FP {c['fp']}, FN {c['fn']})")
    return L


def render_markdown(r: Mapping[str, Any]) -> str:
    c, g, th = r["counts"], r["gate"], r["policy_thresholds"]
    L = ["# Duplicate threshold calibration", "", f"> **{r['caution']}**", ""]
    L += [f"> {n}" for n in r["notes"]] + ([""] if r["notes"] else [])
    L += ["## Inputs", "",
          f"- Gate (`fusion_policy.v1.json` candidate_generation, deterministic and primary): same category = {g['same_category_required']}, radius {g['radius_m']} m, time window {g['time_window_days']} days.",
          f"- Embeddings read from `case_embeddings`: model `{c['model']}`, {c['dimension']} dimensions (models seen: {', '.join(c['models_seen'])}). "
          f"{c['cases_embedded']} of {c['cases']} demo cases have one ({c['cases_missing_embedding']} lack one); {c['involved_embedded']} of the {c['involved']} cases in the pairs below ({c['coverage']:.0%}); "
          f"{c['positives_coverage']:.0%} of the cases of the planted duplicate pairs have a comparable vector.",
          f"- Random sample of out-of-gate pairs: fixed seed {r['seed']}.", "",
          "## Pairs", "",
          f"- Positives: {c['positives_planted']} planted duplicate pairs (`possible_duplicate_pairs`), {c['positives_in_gate']} pass the gate, {c['positives_out_of_gate']} do not (a gate miss no threshold can fix).",
          f"- Not evaluable at case level: {c['merged_signal_pairs_not_evaluable']} report pairs inside merged cases (`duplicate_groups_merged`: one case, one embedding).",
          f"- Hard negatives: {c['near_distinct_in_gate']} of {c['near_distinct_planted']} `near_distinct_pairs` pass the gate; {c['other_gated']} other pairs pass the gate (may hide unlabelled duplicates).",
          f"- Out-of-gate random pairs: {c['out_of_gate_sample']}. Scored (both vectors comparable): {_kv(c['pairs_scored'])}; dropped for a missing or incomparable vector: {_kv(c['pairs_dropped_no_comparable_vector'])}.", "",
          "## Cosine similarity by class", ""]
    L += _dist_table(r["cosine"]["distribution"])
    L += ["", "The out-of-gate row is the baseline: unrelated cases are NOT low, so a bare cosine cutoff cannot replace the gate.", "",
          "## Cosine threshold sweep (inside the gate)", ""] + _sweep_table(r["cosine"]["sweep"])
    L += ["", "## Chosen cosine thresholds", ""] + _chosen_lines(r["cosine"]["chosen"])
    L += [f"- {w}" for w in r["cosine"]["chosen"]["warnings"]]
    f = r["fused"]
    L += ["", "## Against the policy file (fused score)", "",
          f"The thresholds in `fusion_policy.v1.json` (possible_duplicate {th['possible_duplicate']}, related {th['related']}) apply to the FUSED score (cosine + distance + time + category, "
          f"weights status `{f['weights_status']}`), not to the raw cosine above. The same rule applied to the fused score:", ""]
    L += _dist_table(f["distribution"]) + [""] + _chosen_lines(f["chosen"])
    L.append("")
    for name, v in f["versus_policy"].items():
        verdict = "WOULD CHANGE" if v["would_change"] else "no change warranted (within two grid steps)"
        L.append(f"- {name}: policy {v['policy']:.2f} (precision {_f(v['policy_precision'])}, recall {_f(v['policy_recall'])} at the grid point {v['policy_row_threshold']:.2f}) vs chosen {v['chosen']:.2f} "
                 f"(difference {v['difference']:+.2f}): {verdict}")
    L += ["", "The policy file was not edited; applying a change is a decision for a human.", "", "<details><summary>Fused-score sweep</summary>", ""] + _sweep_table(f["sweep"]) + ["", "</details>", ""]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"markdown report (default {DEFAULT_OUT})")
    ap.add_argument("--json-out", type=Path, default=None, help="also write the numbers as JSON")
    ap.add_argument("--city", type=Path, default=DEFAULT_DIR, help="demo city dataset directory")
    ap.add_argument("--samples", type=int, default=500, help="out-of-gate random pairs for the baseline (default 500)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--weights", type=Path, default=None, help="fusion weights for the fused-score section (default: the policy file's prior)")
    a = ap.parse_args(argv)
    city = load_city(a.city)
    policy = load_fusion_policy()
    pairs = build_pairs(city, policy["candidate_generation"], a.samples, a.seed)
    ids = sorted({i for c in ("positives", "near_distinct", "other_gated", "out_of_gate") for p in pairs[c] for i in p})
    vectors = load_vectors(ids)
    try:
        result = calibrate(city, vectors, policy, samples=a.samples, seed=a.seed, weights=FusionWeights.load(a.weights) if a.weights else None, pairs=pairs)
    except CoverageError as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(render_markdown(result), encoding="utf-8", newline="\n")
    if a.json_out:
        a.json_out.parent.mkdir(parents=True, exist_ok=True)
        a.json_out.write_text(json.dumps(result, indent=2), encoding="utf-8", newline="\n")
    c = result["cosine"]["chosen"]
    print(f"{result['caution']}\nreport: {a.out}\npositives scored: {result['counts']['pairs_scored']['positives']}; "
          f"duplicate_threshold {c['duplicate_threshold']['value']:.2f}, related_threshold {c['related_threshold']['value']:.2f} (cosine, inside the gate)")
    for note in [*result["notes"], *result["warnings"]]:
        print(note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
