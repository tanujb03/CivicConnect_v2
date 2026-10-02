"""AI-5 analytics evaluation on the SYNTHETIC demo city (design §11 AI-5, §40).

    python -m ai.evaluation.eval_analytics [--out ai/evaluation/reports] [--name analytics_ai5]

Two separate questions:
  1. FACTS (deterministic, no model): do the reference analytics recover what was planted — hotspots, unusual growth, recurring sites, active incidents —
     and are the facts reproducible, uniquely identified and scoped?
  2. EXPLANATION (the only AI part): with scripted providers, is model prose accepted only when every number and cited fact id is grounded?
     Scripted providers are test doubles, NOT model outputs: this measures the guard rails, not the quality of a real model's wording.
NOT measured: how well a real LLM explains the facts (needs a provider; see the live-provider test) or whether staff find the text useful.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from ai.evaluation.analytics_facts import build_fact_set
from ai.evaluation.analytics_reference import subcategory_growth
from ai.evaluation.eval_demo_city import load_city
from ai.evaluation.provenance import build_provenance, claims_for, validate_track
from ai.evaluation.run_eval import HERE, write_report
from ai.inference.analytics.service import AnalyticsExplainer
from ai.inference.config import load_taxonomy
from ai.inference.grounding import allowed_numbers, ungrounded_numbers
from ai.inference.providers.fake import FakeProvider
from ai.inference.schemas import AnalyticsFactSet

NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)


def _facts(d: dict, cases: list[dict], label: str) -> AnalyticsFactSet:
    return build_fact_set(cases, {w["id"]: w for w in d["wards"]}, {x["id"]: x for x in d["departments"]}, d["incidents"], NOW, scope_label=label)


def scopes(d: dict) -> list[tuple[str, AnalyticsFactSet]]:
    out = [("city", _facts(d, d["cases"], "Synthetic demo city"))]
    for w in d["wards"][:3]:
        out.append((f"ward {w['label']}", _facts(d, [c for c in d["cases"] if c["ward_id"] == w["id"]], f"Synthetic demo city, ward {w['label']}")))
    for dep in d["departments"][:3]:
        out.append((f"department {dep['id']}", _facts(d, [c for c in d["cases"] if c["department_id"] == dep["id"]], f"Synthetic demo city, {dep['name']}")))
    return out


def _honest(fs: AnalyticsFactSet) -> FakeProvider:
    top = fs.facts[:3]
    return FakeProvider(structured={"analytics": {"summary": f"{fs.scope_label}: " + "; ".join(f"{f.metric} {f.value}" for f in top) + ".",
                                                  "highlights": [{"text": f"{f.metric}: {f.value}", "fact_ids": [f.id]} for f in top]}})


def _hallucinating(fs: AnalyticsFactSet) -> FakeProvider:
    return FakeProvider(structured={"analytics": {"summary": "Cases rose 47% and 913 are overdue.", "highlights": [{"text": "47% rise", "fact_ids": [fs.facts[0].id]}]}})


def _bad_ids(fs: AnalyticsFactSet) -> FakeProvider:
    f = fs.facts[0]
    return FakeProvider(structured={"analytics": {"summary": f"{f.metric} {f.value}.", "highlights": [{"text": f"{f.metric} {f.value}", "fact_ids": ["f999"]}]}})


def _final_text_grounded(r, fs: AnalyticsFactSet) -> bool:
    allowed = allowed_numbers([fs.scope_label] + [x for f in fs.facts for x in (f.value, f.period, f.unit, f.metric)])
    return not ungrounded_numbers(r.summary + " " + " ".join(h.text for h in r.highlights), allowed)


def evaluate(d: dict) -> dict:
    gt = d["ground_truth"]
    city = _facts(d, d["cases"], "Synthetic demo city")
    text = " | ".join(f.metric for f in city.facts)
    planted_hot = {h["subcategory"].replace("_", " ") for h in gt["hotspots"]}
    planted_rec = {s["subcategory"].replace("_", " ") for s in gt["recurring_sites"]}
    growth = {i["subcategory"] for i in subcategory_growth(d["cases"], NOW)["items"]}
    planted_hot_raw = {h["subcategory"] for h in gt["hotspots"]}
    by_id = {c["id"]: c for c in d["cases"]}
    incident_subs = {by_id[cid]["subcategory"] for ids in gt["incident_cases"].values() for cid in ids if cid in by_id}   # planted incidents also raise their categories
    active = [i for i in d["incidents"] if i["status"] == "ACTIVE"]
    facts_block = {
        "hotspot_recall": round(sum(f"hotspot: {s}" in text for s in planted_hot) / len(planted_hot), 4),
        "growth_recall_of_planted_hotspot_subcategories": round(len(growth & planted_hot_raw) / len(planted_hot_raw), 4),
        "growth_explained_by_planted_incidents": sorted((growth - planted_hot_raw) & incident_subs),
        "growth_unexplained_subcategories": sorted(growth - planted_hot_raw - incident_subs),
        "recurring_sites_recall_in_facts": round(sum(f"recurring problem: {s}" in text for s in planted_rec) / len(planted_rec), 4),
        "recurring_note": "Facts list only the top 5 recurring sites, so recall below 1.0 is a display cap, not a detection failure (see demo-city recovery).",
        "active_incident_recall": round(sum(any(i["id"] == f.ref_id for f in city.facts) for i in active) / len(active), 4),
        "reproducible": scopes(d)[0][1].model_dump() == scopes(d)[0][1].model_dump() and _facts(d, d["cases"], "Synthetic demo city").model_dump() == city.model_dump(),
        "fact_ids_unique": all(len({f.id for f in fs.facts}) == len(fs.facts) for _, fs in scopes(d)),
        "n_facts_city": len(city.facts),
    }
    dep = [x for x in d["departments"]][0]["id"]
    dep_facts = _facts(d, [c for c in d["cases"] if c["department_id"] == dep], "dept")
    facts_block["department_scope_total_matches"] = next(f.value for f in dep_facts.facts if f.metric == "total cases in scope") == sum(c["department_id"] == dep for c in d["cases"])

    rows = {"honest": [], "hallucinating": [], "bad_ids": [], "no_provider": []}
    for _, fs in scopes(d):
        for kind, prov in (("honest", _honest(fs)), ("hallucinating", _hallucinating(fs)), ("bad_ids", _bad_ids(fs)), ("no_provider", None)):
            r = AnalyticsExplainer(prov).explain(fs)
            rows[kind].append((r, fs))
    n = len(rows["honest"])
    top_hot = [f for f in city.facts if f.metric.startswith("hotspot:")]
    template = rows["no_provider"][0][0].summary
    explain_block = {
        "scopes_tested": n,
        "honest_provider_prose_accepted": round(sum(r.ai_metadata.source == "provider" for r, _ in rows["honest"]) / n, 4),
        "hallucinated_numbers_rejected_and_replaced": round(sum(r.ai_metadata.source == "rules" and any(w.startswith("EXPLANATION_UNGROUNDED_FALLBACK") for w in r.warnings)
                                                                for r, _ in rows["hallucinating"]) / n, 4),
        "unknown_fact_ids_rejected_and_replaced": round(sum(r.ai_metadata.source == "rules" for r, _ in rows["bad_ids"]) / n, 4),
        "ungrounded_numbers_in_any_final_output": sum(not _final_text_grounded(r, fs) for kind in rows for r, fs in rows[kind]),
        "template_summary_mentions_planted_hotspot_when_present": all(h.metric in template for h in top_hot[:3]) if top_hot else None,
        "all_outputs_grounded_flag": all(r.grounded for kind in rows for r, _ in rows[kind]),
    }
    return {"task": "analytics_ai5", "facts": facts_block, "explanation_guard_rails": explain_block,
            "not_evaluated": ["quality/usefulness of a real LLM's wording", "multilingual explanations", "staff comprehension"],
            "provider_note": "Providers in this report are scripted test doubles, not model outputs."}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=HERE / "reports")
    ap.add_argument("--name", default="analytics_ai5")
    a = ap.parse_args(argv)
    d = load_city()
    prov = build_provenance([{"synthetic": True}] * len(d["cases"]))
    validate_track("synthetic", prov)
    claims = claims_for("synthetic", prov)
    p = write_report(a.out, a.name, {"track": "synthetic", "task": "analytics_ai5", "system": "rules+scripted", "artifact": None, "datasets": {"demo_city_v1": "demo_city_v1"},
                                     "taxonomy_version": load_taxonomy().version, "provenance": prov, "claims": claims, "results": evaluate(d)})
    print("report:", p, "\nbanner:", claims["banner"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
