"""AI-5: deterministic facts recover the planted demo-city truth; explanations are accepted only when grounded."""
import json
from datetime import datetime, timezone

from ai.evaluation import eval_analytics
from ai.evaluation.analytics_reference import geographic_concentration, sla_risk, subcategory_growth
from ai.evaluation.eval_demo_city import load_city
from ai.evaluation.run_eval import HERE

FLOORS = json.loads((HERE / "regression_floors.json").read_text(encoding="utf-8"))["analytics_ai5"]
D = load_city()
NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)
R = eval_analytics.evaluate(D)


def test_facts_recover_the_planted_truth():
    f = R["facts"]
    assert f["hotspot_recall"] >= FLOORS["hotspot_recall_min"]
    assert f["growth_recall_of_planted_hotspot_subcategories"] >= FLOORS["growth_recall_min"] and f["growth_unexplained_subcategories"] == []
    assert f["active_incident_recall"] >= FLOORS["active_incident_recall_min"]
    assert f["reproducible"] and f["fact_ids_unique"] and f["department_scope_total_matches"]


def test_explanation_guard_rails():
    e = R["explanation_guard_rails"]
    assert e["hallucinated_numbers_rejected_and_replaced"] >= FLOORS["hallucination_rejection_min"] and e["unknown_fact_ids_rejected_and_replaced"] == 1.0
    assert e["ungrounded_numbers_in_any_final_output"] <= FLOORS["ungrounded_numbers_max"] and e["honest_provider_prose_accepted"] == 1.0
    assert e["template_summary_mentions_planted_hotspot_when_present"] is True
    assert "quality/usefulness of a real LLM's wording" in R["not_evaluated"]


def test_growth_is_relative_to_the_city_trend_not_absolute():
    g = subcategory_growth(D["cases"], NOW)
    assert g["city_growth_ratio"] > 1.5                      # the demo city as a whole is growing...
    planted = {h["subcategory"] for h in D["ground_truth"]["hotspots"]}
    incident = {c["subcategory"] for c in D["cases"] if c["id"] in {x for ids in D["ground_truth"]["incident_cases"].values() for x in ids}}
    found = {i["subcategory"] for i in g["items"]}
    assert planted <= found <= planted | incident            # ...only planted hotspots and subcategories of planted incidents stand out
    assert subcategory_growth(D["cases"], NOW, min_relative_ratio=50)["items"] == []


def test_sla_risk_and_concentration_are_consistent_with_the_cases():
    r = sla_risk(D["cases"], NOW)
    assert r["breached"] == sum(c["status"] not in ("RESOLVED", "VERIFIED", "REJECTED") and c["sla_deadline"] < "2026-10-01T00:00:00Z" for c in D["cases"])
    assert sum(x["breached"] for x in r["breached_by_department"]) == r["breached"]
    g = geographic_concentration(D["cases"], NOW)
    assert 0 < g["top_k_share_pct"] <= 100 and len(g["top_wards"]) == 3 and g["top_wards"][0]["cases"] >= g["top_wards"][1]["cases"]
