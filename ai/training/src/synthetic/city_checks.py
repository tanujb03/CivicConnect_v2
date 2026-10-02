"""Validation of the synthetic demo city: §58 minimums, referential integrity, §35 state-machine legality, labelling, and
recoverability of the planted ground truth by the deterministic reference analytics. Returns a list of problems (empty = valid)."""
from __future__ import annotations

from datetime import datetime, timezone

from ai.evaluation.analytics_reference import hotspots, recurring_sites
from ai.inference.config import load_taxonomy

from .city import LEGAL, NOW, TERMINAL

MINIMUMS = {"wards": 10, "departments": 8, "cases": 500, "categories": 8, "merged_duplicate_groups": 20, "possible_duplicate_pairs": 15, "recurring_sites": 10,
            "sla_breached": 30, "resolved": 100, "reopened": 20, "active_incidents": 3}
COLLECTIONS = ("wards", "departments", "users", "cases", "report_signals", "case_relations", "status_events", "work_orders", "verifications", "incidents")


def counts(d: dict) -> dict:
    c = d["cases"]
    return {"wards": len(d["wards"]), "departments": len(d["departments"]), "users": len(d["users"]), "cases": len(c), "report_signals": len(d["report_signals"]),
            "categories": len({x["category"] for x in c if x["category"] != "other"}), "merged_duplicate_groups": len(d["ground_truth"]["duplicate_groups_merged"]),
            "possible_duplicate_pairs": len(d["ground_truth"]["possible_duplicate_pairs"]), "recurring_sites": len(d["ground_truth"]["recurring_sites"]),
            "sla_breached": sum(x["sla_breached"] for x in c), "resolved": sum(x["status"] == "RESOLVED" for x in c), "reopened": sum(x["reopen_count"] > 0 for x in c),
            "currently_reopened": sum(x["status"] == "REOPENED" for x in c), "rejected": sum(x["status"] == "REJECTED" for x in c),
            "open": sum(x["status"] not in TERMINAL for x in c), "active_incidents": sum(i["status"] == "ACTIVE" for i in d["incidents"]), "incidents": len(d["incidents"]),
            "multilingual_signals": {lang: sum(s["original_language"] == lang for s in d["report_signals"]) for lang in ("en", "hi", "mr", "hi-Latn")}}


def recovery(d: dict) -> dict:
    """How well the deterministic reference analytics recover the planted truth (precision = share of detected sites that are planted)."""
    cases = d["cases"]
    sites = recurring_sites(cases)
    planted = {frozenset(s["case_ids"]) for s in d["ground_truth"]["recurring_sites"]}
    hit = sum(any(p <= set(s["case_ids"]) for s in sites) for p in planted)
    gt = d["ground_truth"]
    structured = ({i for g in gt["duplicate_groups_merged"] for i in [g["case_id"]]} | {i for r in gt["recurring_sites"] for i in r["case_ids"]}
                  | {i for h in gt["hotspots"] for i in h["case_ids"]} | {i for ids in gt["incident_cases"].values() for i in ids}
                  | {i for r in gt["possible_duplicate_pairs"] + gt["near_distinct_pairs"] for i in (r["case_a"], r["case_b"])})
    detected_planted = sum(any(p <= set(s["case_ids"]) for p in planted) for s in sites)
    unexplained = sum(not (set(s["case_ids"]) & structured) for s in sites)
    hs = hotspots(cases, NOW)
    hp = d["ground_truth"]["hotspots"]
    h_hit = sum(any(set(g["case_ids"]) & set(h["case_ids"]) and h["subcategory"] == g["subcategory"] for h in hs) for g in hp)
    return {"recurring": {"planted": len(planted), "recovered": hit, "recall": round(hit / max(len(planted), 1), 3), "detected": len(sites),
                          "detected_that_are_planted": detected_planted, "detected_but_from_other_planted_structures": len(sites) - detected_planted - unexplained,
                          "unexplained_by_any_planted_structure": unexplained},
            "hotspots": {"planted": len(hp), "recovered": h_hit, "recall": round(h_hit / max(len(hp), 1), 3), "detected": len(hs)}}


def validate_city(d: dict) -> list[str]:
    p: list[str] = []
    for k in COLLECTIONS:
        if k not in d or not d[k]:
            p.append(f"collection {k} missing or empty")
    if p:
        return p
    t = load_taxonomy()
    c = counts(d)
    for k, mn in MINIMUMS.items():
        if c[k] < mn:
            p.append(f"§58 minimum not met: {k} = {c[k]} < {mn}")
    for name in COLLECTIONS:                                                 # everything is labelled synthetic
        bad = [r.get("id") for r in d[name] if r.get("synthetic") is not True]
        if bad:
            p.append(f"{name}: {len(bad)} record(s) not labelled synthetic")
    ids = {k: {r["id"] for r in d[k]} for k in ("wards", "departments", "users", "cases", "report_signals", "incidents")}
    for r in d["cases"]:
        if r["ward_id"] not in ids["wards"] or (r["department_id"] not in ids["departments"] and not (r["department_id"] is None and r["subcategory"] == "unclassified")):
            p.append(f"case {r['id']}: dangling ward/department")
        if r["incident_id"] and r["incident_id"] not in ids["incidents"]:
            p.append(f"case {r['id']}: dangling incident")
        sub = t.subcategories[r["subcategory"]]
        if sub.category_id != r["category"] or sub.department_id != r["department_id"]:
            p.append(f"case {r['id']}: category/department disagree with taxonomy")
        if r["sla_hours"] != t.sla_hours[r["sla_class"]]:
            p.append(f"case {r['id']}: sla_hours does not match sla_class")
        if (r["closed_at"] is not None) != (r["status"] in TERMINAL):
            p.append(f"case {r['id']}: closed_at inconsistent with status {r['status']}")
        if not str(r["public_case_id"]).startswith("DEMO-"):
            p.append(f"case {r['id']}: public id is not DEMO-prefixed")
    for s in d["report_signals"]:
        if s["case_id"] not in ids["cases"] or s["reporter_id"] not in ids["users"]:
            p.append(f"signal {s['id']}: dangling reference")
    for r in d["case_relations"]:
        if r["case_a"] not in ids["cases"] or r["case_b"] not in ids["cases"] or r["case_a"] == r["case_b"]:
            p.append(f"relation {r['id']}: invalid")
    by_case: dict[str, list] = {}
    for e in d["status_events"]:
        by_case.setdefault(e["case_id"], []).append(e)
    cases = {x["id"]: x for x in d["cases"]}
    for cid, evs in by_case.items():
        evs.sort(key=lambda e: e["at"])
        if evs[0]["from_state"] is not None or evs[0]["to_state"] != "SUBMITTED":
            p.append(f"case {cid}: lifecycle does not start at SUBMITTED")
        for a, b in zip(evs, evs[1:], strict=False):
            if b["to_state"] not in LEGAL[a["to_state"]] or b["from_state"] != a["to_state"]:
                p.append(f"case {cid}: illegal transition {a['to_state']} -> {b['to_state']}")
        if cases[cid]["status"] != evs[-1]["to_state"]:
            p.append(f"case {cid}: status {cases[cid]['status']} != last event {evs[-1]['to_state']}")
        if datetime.fromisoformat(evs[-1]["at"].replace("Z", "+00:00")) > NOW.astimezone(timezone.utc):
            p.append(f"case {cid}: event in the future")
    if set(by_case) != set(cases):
        p.append("some cases have no lifecycle events")
    rec = recovery(d)
    if rec["recurring"]["recall"] < 0.9:
        p.append(f"planted recurring sites not recoverable by the reference analytics: {rec['recurring']}")
    if rec["recurring"]["unexplained_by_any_planted_structure"]:
        p.append(f"reference analytics found recurring sites that no planted structure explains (ground truth incomplete): {rec['recurring']}")
    if rec["hotspots"]["recall"] < 1.0:
        p.append(f"planted hotspots not recoverable by the reference analytics: {rec['hotspots']}")
    return p
