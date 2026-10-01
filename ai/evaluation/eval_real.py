"""Evaluations that only make sense on REAL public data (see training/src/data_sources cards).

* taxonomy coverage  -- how real civic demand lands in taxonomy v1 (and which labels have no real examples)
* real fusion        -- agency-linked duplicate pairs: geo/time/category behaviour on real data
* vision             -- provider vision path on RDD2022 road-damage images (needs a configured provider)
* real intake        -- text classification, ONLY when genuine citizen narrative exists (guarded)
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Sequence

import numpy as np

from ai.evaluation import eval_fusion, eval_intake
from ai.evaluation import metrics as M
from ai.evaluation.provenance import TrackError
from ai.inference.config import load_taxonomy
from ai.inference.fusion.scoring import FusionWeights
from ai.inference.intake.service import IntakeService
from ai.inference.schemas import EvidenceInput, IntakeRequest
from ai.training.src.data_sources.canonical import CaseRecord
from ai.training.src.data_sources.column_roles import TaskPolicy
from ai.training.src.data_sources.leakage import audit_task, censoring_report
from ai.training.src.data_sources.mapping import DepartmentMapping
from ai.training.src.data_sources.splits import grid_cell


def evaluate_taxonomy_coverage(records: Sequence[dict]) -> dict:
    t = load_taxonomy()
    status = Counter(r["mapping_status"] for r in records)
    labels = Counter(f"{r['category']}/{r['subcategory']}" for r in records if r.get("subcategory"))
    cats = Counter(r["category"] for r in records if r.get("category"))
    n = max(len(records), 1)
    unmapped = Counter(f"{r.get('source_category')} | {r.get('source_subcategory')}" for r in records if r["mapping_status"] == "unmapped")
    out_scope = Counter(f"{r.get('source_category')}" for r in records if r["mapping_status"] == "out_of_scope")
    return {
        "task": "taxonomy_coverage", "n": len(records),
        "mapping_status_share": {k: round(v / n, 4) for k, v in sorted(status.items())},
        "mapped_to_subcategory_share": round(status.get("exact", 0) / n, 4),
        "mapped_any_share": round((status.get("exact", 0) + status.get("category_only", 0)) / n, 4),
        "category_distribution": dict(cats.most_common()),
        "subcategory_distribution": dict(labels.most_common()),
        "taxonomy_subcategories_with_no_real_examples": sorted(set(t.label_ids) - set(labels)),
        "top_unmapped_source_labels": unmapped.most_common(25),
        "top_out_of_scope_source_labels": out_scope.most_common(15),
        "interpretation": ("Describes demand coverage of OUR taxonomy under a DRAFT mapping. It is not a model-accuracy metric. Subcategories "
                           "with no real examples are where synthetic augmentation (or partner data) is needed."),
    }


def evaluate_real_fusion(pairs: Sequence[dict], weights: FusionWeights | None = None) -> dict:
    res = eval_fusion.evaluate(list(pairs), weights)
    pos = [p for p in pairs if p["label"] == 1]
    res["real_data_notes"] = {
        "positives": len(pos), "negatives": len(pairs) - len(pos),
        "positives_with_differing_category": sum(p["a"]["category"] != p["b"]["category"] for p in pos),
        "semantic_signal": "not evaluated: real 311 rows carry no narrative text (semantic fixed at 0)",
        "label_noise": "negatives are unlinked nearby same-type requests and may include real duplicates the agency never linked",
    }
    res.pop("caveat", None)
    res["caveat"] = ("REAL agency-linked duplicates; geo/time/category signals only. Single city; labels are agency-assigned, not independently verified.")
    return res


def evaluate_intake_real(service: IntakeService, records: Sequence[dict]) -> dict:
    if any(r.get("text_origin") != "citizen_narrative" for r in records):
        raise TrackError("no usable real narrative text (text_origin != citizen_narrative): refusing to score a classifier on category text")
    rows = [{"text": r["text"], "category": r["category"], "subcategory": r["subcategory"], "department": r.get("department"),
             "language": r.get("language")} for r in records if r.get("mapping_status") == "exact"]
    return eval_intake.evaluate(service, rows)


def evaluate_vision(service: IntakeService, records: Sequence[dict], image_root: Path, *, max_per_country: int = 100, seed: int = 0,
                    max_image_bytes: int | None = None) -> dict:
    """Run the provider's multimodal intake on RDD2022 images and compare with the mapped annotations.

    Requires a provider (a text classifier cannot see images). Per-country sampling is stratified and seeded.
    Gold: ``roads/pothole`` in image_labels => pothole present; any road label => road damage present."""
    if service.provider is None:
        raise TrackError("vision evaluation needs a configured provider (OPENAI_API_KEY + AI_INTAKE_MODEL); none available")
    rng = random.Random(seed)
    by_country: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        if r.get("has_annotation"):
            by_country[r.get("country") or r["provenance"]["source_id"]].append(r)
    limit = max_image_bytes or service.policy.intake["max_image_bytes"]
    rows, skipped = [], Counter()
    for country, recs in sorted(by_country.items()):
        recs = sorted(recs, key=lambda r: r["record_id"])
        rng.shuffle(recs)
        for r in recs[:max_per_country]:
            p = Path(image_root) / r["image_relpath"]
            if not p.is_file():
                skipped["missing_image"] += 1
                continue
            data = p.read_bytes()
            if len(data) > limit:
                skipped["too_large"] += 1
                continue
            mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
            resp = service.analyze(IntakeRequest(evidence=[EvidenceInput(evidence_id=r["record_id"], media_type="IMAGE", data=data, mime_type=mime)]))
            rows.append({"country": country, "gold_pothole": "roads/pothole" in r["image_labels"], "gold_road": any(l.startswith("roads") for l in r["image_labels"]),
                         "pred_pothole": resp.proposal.category == "roads" and resp.proposal.subcategory == "pothole",
                         "pred_road": resp.proposal.category == "roads", "degraded": resp.ai_metadata.degraded})
    if not rows:
        raise TrackError("no images could be evaluated")
    degraded = sum(x["degraded"] for x in rows) / len(rows)

    def block(sel):
        pot = M.precision_recall_at([float(x["pred_pothole"]) for x in sel], [int(x["gold_pothole"]) for x in sel], 0.5)
        rate = sum(x["gold_pothole"] for x in sel) / len(sel)
        return {"n": len(sel), "pothole_precision_valid": 0 < rate < 0.99, "pothole_precision": round(pot["precision"], 4), "pothole_recall": round(pot["recall"], 4),
                "pothole_f1": round(pot["f1"], 4), "road_damage_recall": round(sum(x["pred_road"] for x in sel if x["gold_road"]) / max(sum(x["gold_road"] for x in sel), 1), 4),
                "gold_pothole_rate": round(sum(x["gold_pothole"] for x in sel) / len(sel), 4)}

    return {"task": "vision", "n": len(rows), "overall": block(rows), "by_country": {c: block([x for x in rows if x["country"] == c]) for c in sorted({x["country"] for x in rows})},
            "degraded_rate": round(degraded, 4), "skipped": dict(skipped), "max_per_country": max_per_country,
            "validity": "INVALID: provider degraded on >10% of images" if degraded > 0.1 else "ok",
            "group_key": "country, or the source id when the dataset has no country field",
            "precision_note": "pothole precision is only meaningful when the evaluated images include negatives (pothole_precision_valid=true)",
            "caveat": ("Road-survey images, not citizen close-ups; cracks have no taxonomy subcategory so only pothole (D40) is scored at subcategory level; "
                       "random image sampling within a country can leak near-identical road sequences between prompt-tuning and test use.")}


# --------------------------------------------------------------------------------------------------------------------
# BMC Mumbai (descriptive) tasks: every function reads records ONLY through the column-role TaskPolicy view.
# --------------------------------------------------------------------------------------------------------------------
def _cases(rows: Sequence[dict]) -> list[CaseRecord]:
    recs = [CaseRecord.model_validate(r) for r in rows]
    if any(r.provenance.source_id != "bmc_mumbai" for r in recs):
        raise TrackError("these evaluations apply to prepared bmc_mumbai records (column-role policy)")
    return recs


def _q(values: list[float], q: float) -> float:
    return round(float(np.percentile(values, q)), 2)


def evaluate_resolution_time_prior(rows: Sequence[dict], policy: TaskPolicy | None = None) -> dict:
    policy = policy or TaskPolicy.load("bmc_mumbai")
    recs = _cases(rows)
    task = "resolution_time_prior"
    views = [(policy.view(r, task), r) for r in recs]
    durations = [(v.inputs.get("category") or "(unmapped)", v.inputs.get("ward"), v.targets["resolution_hours"]) for v, _ in views if v.targets.get("resolution_hours") is not None]
    if not durations:
        raise TrackError("no resolution durations available (closed_at/resolution_duration missing, or unit unknown): resolution_time_prior cannot run")
    sla = load_taxonomy().sla_hours

    def block(vals: list[float]) -> dict:
        return {"n": len(vals), "median_h": _q(vals, 50), "p75_h": _q(vals, 75), "p90_h": _q(vals, 90),
                "share_over_sla_hours": {k: round(sum(v > h for v in vals) / len(vals), 4) for k, h in sorted(sla.items(), key=lambda kv: kv[1])}}

    by_cat: dict[str, list[float]] = defaultdict(list)
    by_ward: dict[str, list[float]] = defaultdict(list)
    for cat, ward, h in durations:
        by_cat[cat].append(h)
        by_ward[str(ward)].append(h)
    ins, tgts = policy.allowed_roles(task)
    return {"task": task, "n": len(recs), "inputs_used": ins, "targets_used": tgts,
            "roles_never_read": sorted(policy.effective_forbidden(task)), "overall": block([d[2] for d in durations]),
            "by_category": {k: block(v) for k, v in sorted(by_cat.items(), key=lambda kv: -len(kv[1])) if len(v) >= 5},
            "by_ward_top10": {k: block(v) for k, v in sorted(by_ward.items(), key=lambda kv: -len(kv[1]))[:10] if len(v) >= 5},
            "censoring": censoring_report(recs), "sla_reference_hours": sla, "leakage": audit_task(recs, policy, task),
            "interpretation": ("Distribution of resolution durations among RESOLVED complaints only (the rest are censored) in a dataset whose origin is unverified. "
                               "A sanity reference for SLA hours, not a prediction model and not a real-world claim.")}


def evaluate_recurrence_hotspot(rows: Sequence[dict], policy: TaskPolicy | None = None, *, cell_deg: float = 0.00135, min_cases: int = 4, window_days: float = 240.0) -> dict:
    policy = policy or TaskPolicy.load("bmc_mumbai")
    recs = _cases(rows)
    task = "recurrence_hotspot"
    cells: dict[tuple, list] = defaultdict(list)
    n_loc = 0
    for r in recs:
        v = policy.view(r, task).inputs
        if v["latitude"] is None or v["longitude"] is None or v["created_at"] is None or not v["category"]:
            continue
        n_loc += 1
        cells[(v["category"], grid_cell(v["latitude"], v["longitude"], cell_deg))].append((datetime.fromisoformat(v["created_at"]), v["ward"]))
    recurrent = {}
    for k, items in cells.items():
        items.sort()
        # a recurrent site: >= min_cases within any window of window_days
        j = 0
        for i in range(len(items)):
            while (items[i][0] - items[j][0]).days > window_days:
                j += 1
            if i - j + 1 >= min_cases:
                recurrent[k] = items
                break
    wards = Counter(w for items in recurrent.values() for _, w in items)
    top = sorted(recurrent.items(), key=lambda kv: -len(kv[1]))[:10]
    ins, _ = policy.allowed_roles(task)
    return {"task": task, "n": len(recs), "n_with_location_time_category": n_loc, "inputs_used": ins, "roles_never_read": sorted(policy.effective_forbidden(task)),
            "definition": f"same mapped category within a ~{int(cell_deg * 111000)} m cell, >= {min_cases} complaints inside {int(window_days)} days (design §38 style)",
            "n_cells": len(cells), "n_recurrent_cells": len(recurrent), "complaints_in_recurrent_cells": sum(len(v) for v in recurrent.values()),
            "share_of_located_complaints_in_recurrent_cells": round(sum(len(v) for v in recurrent.values()) / max(n_loc, 1), 4),
            "recurrent_cells_by_category": dict(Counter(k[0] for k in recurrent)), "top_wards_by_recurrent_complaints": wards.most_common(10),
            "top_recurrent_cells": [{"category": k[0], "cell": k[1], "complaints": len(v)} for k, v in top], "leakage": audit_task(recs, policy, task),
            "interpretation": "Validates that the deterministic recurrence/hotspot definition produces sensible, non-degenerate output on a large ward-level complaint set. Descriptive; origin unverified."}


def evaluate_routing_agreement(rows: Sequence[dict], policy: TaskPolicy | None = None, dept_mapping: DepartmentMapping | None = None) -> dict:
    policy = policy or TaskPolicy.load("bmc_mumbai")
    dm = dept_mapping or DepartmentMapping.load("bmc_mumbai_departments")
    t = load_taxonomy()
    recs = _cases(rows)
    task = "routing_agreement"
    pairs = []
    n_dept = n_dept_mapped = 0
    for r in recs:
        v = policy.view(r, task)
        raw = v.targets.get("department")
        if raw is None or not v.inputs.get("category"):
            continue
        n_dept += 1
        theirs = dm.map(str(raw))
        n_dept_mapped += theirs is not None
        if theirs is not None:
            pairs.append((v.inputs["category"], t.department_for(v.inputs["category"], v.inputs.get("subcategory")), theirs))
    if not n_dept:
        raise TrackError("no rows with both a mapped category and a recorded department: routing_agreement cannot run")
    agree = sum(a == b for _, a, b in pairs)
    per_cat: dict[str, list[bool]] = defaultdict(list)
    for c, a, b in pairs:
        per_cat[c].append(a == b)
    audit = audit_task(recs, policy, task)
    return {"task": task, "n": len(recs), "rows_with_category_and_department": n_dept, "department_mapped_share": round(n_dept_mapped / n_dept, 4),
            "comparable_pairs": len(pairs), "agreement": round(agree / len(pairs), 4) if pairs else None,
            "agreement_by_category": {c: {"n": len(v), "agreement": round(sum(v) / len(v), 4)} for c, v in sorted(per_cat.items())},
            "top_disagreements": Counter((a, b) for _, a, b in pairs if a != b).most_common(10),
            "inputs_used": policy.allowed_roles(task)[0], "targets_used": policy.allowed_roles(task)[1], "roles_never_read": sorted(policy.effective_forbidden(task)),
            "leakage": audit,
            "interpretation": ("Agreement between the source's recorded department (mapped to ours by a DRAFT keyword mapping) and our category->department routing. It is a consistency "
                               "check of two label systems, NOT model accuracy; if the source department is a deterministic function of its category (see leakage.purity) the comparison is vacuous.")}


def evaluate_triage_priority_prior(rows: Sequence[dict], policy: TaskPolicy | None = None) -> dict:
    policy = policy or TaskPolicy.load("bmc_mumbai")
    recs = _cases(rows)
    task = "triage_priority_prior"
    dist: dict[str, dict[str, Counter]] = {"severity": defaultdict(Counter), "priority": defaultdict(Counter)}
    n = {"severity": 0, "priority": 0}
    for r in recs:
        v = policy.view(r, task)
        for tgt in ("severity", "priority"):
            val = v.targets.get(tgt)
            if val is not None:
                n[tgt] += 1
                dist[tgt][v.inputs.get("category") or "(unmapped)"][str(val)] += 1
    if not (n["severity"] or n["priority"]):
        raise TrackError("no severity/priority values in the prepared records: triage_priority_prior cannot run")
    return {"task": task, "n": len(recs), "rows_with_target": n, "inputs_used": policy.allowed_roles(task)[0], "targets_used": policy.allowed_roles(task)[1],
            "roles_never_read": sorted(policy.effective_forbidden(task)),
            "distribution_by_category": {k: {c: dict(v) for c, v in sorted(d.items())} for k, d in dist.items() if d}, "leakage": audit_task(recs, policy, task),
            "interpretation": ("Recorded severity/priority distributions by category: descriptive priors to sanity-check our priority-score ranges. The provenance of these labels is "
                               "unknown; they are never ground truth, and no triage model is trained on them.")}
