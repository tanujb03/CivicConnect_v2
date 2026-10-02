"""Deterministic AI-5 FACTS (design §40: "deterministic aggregation produces the facts, the LLM explains them").

``build_fact_set`` is the executable specification of what the backend's SQL must hand to ``AIService.explain_analytics``: ids are stable, values are
display-ready (so a model quoting "27%" is checkable against the fact verbatim), and every fact carries a citation reference. Nothing here uses a model.
"""
from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime
from typing import Mapping, Sequence

from ai.evaluation.analytics_reference import (
    RESOLVED_STATES,
    geographic_concentration,
    hotspots,
    recurring_sites,
    sla_risk,
    subcategory_growth,
)
from ai.inference.schemas import AnalyticsFact, AnalyticsFactSet


def _ref(*parts: object) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "civicconnect-demo-analytic/" + "/".join(map(str, parts))))


def _pretty(sub: str) -> str:
    return sub.replace("_", " ")


def build_fact_set(cases: Sequence[Mapping], wards: Mapping[str, Mapping], departments: Mapping[str, Mapping], incidents: Sequence[Mapping], now: datetime, *,
                   scope_label: str, max_items: int = 5) -> AnalyticsFactSet:
    """``cases`` must already be restricted to the caller's scope (ward / department / role)."""
    facts: list[AnalyticsFact] = []

    def add(metric: str, value, *, unit: str | None = None, period: str | None = None, ref_type: str = "ANALYTIC", ref_id: str | None = None) -> None:
        facts.append(AnalyticsFact(id=f"f{len(facts) + 1:02d}", metric=metric, value=value, unit=unit, period=period, ref_type=ref_type,  # type: ignore[arg-type]
                                   ref_id=ref_id or _ref("fact", metric, period or "")))

    label = lambda w: (wards.get(w) or {}).get("label", "unknown ward")      # noqa: E731
    dep_name = lambda d: (departments.get(d) or {}).get("name", d)             # noqa: E731

    # Ordered by urgency, because the deterministic template fallback quotes only the first facts: incidents, hotspots, unusual growth, then SLA, then context.
    for inc in [i for i in incidents if i.get("status") == "ACTIVE"][:3]:
        add(f"active incident: {inc['title']}", 1, unit="incident", ref_type="INCIDENT", ref_id=inc["id"])
    for h in hotspots(cases, now)[:max_items]:
        add(f"hotspot: {_pretty(h['subcategory'])}, recent cases in one 350 m cell", h["recent_cases"], unit="cases", period="14 days",
            ref_id=_ref("hotspot", h["subcategory"], *h["cell"]))
    for it in subcategory_growth(cases, now)["items"][:max_items]:
        add(f"unusual growth: {_pretty(it['subcategory'])}, rate vs the city-wide trend", f"{it['relative_growth']}x", period="14 days vs previous 90 days",
            ref_id=_ref("growth", it["subcategory"]))
    statuses = Counter(c["status"] for c in cases)
    open_n = sum(v for k, v in statuses.items() if k not in RESOLVED_STATES)
    risk = sla_risk(cases, now)
    if open_n:
        add("open cases past their SLA deadline", risk["breached"], unit="cases", ref_id=_ref("sla_risk", "breached"))
        add("open cases due within 24 hours", risk["due_within_horizon"], unit="cases", ref_id=_ref("sla_risk", "due"))
        for row in risk["breached_by_department"][:3]:
            add(f"SLA breaches, {dep_name(row['department_id'])}", row["breached"], unit="cases", ref_id=_ref("sla_risk", row["department_id"]))
    for s in recurring_sites(cases)[:max_items]:
        add(f"recurring problem: {_pretty(s['subcategory'])}, cases at one site", s["n_cases"], unit="cases", period="240 days",
            ref_id=_ref("recurrence", s["subcategory"], s["center"]["latitude"], s["center"]["longitude"]))
        if s["n_reopened"]:
            add(f"reopened cases at the {_pretty(s['subcategory'])} site", s["n_reopened"], unit="cases",
                ref_id=_ref("recurrence", s["subcategory"], s["center"]["latitude"], "reopened"))
    conc = geographic_concentration(cases, now)
    if conc["recent_cases"]:
        names = ", ".join(label(w["ward_id"]) for w in conc["top_wards"])
        add(f"share of recent cases in the 3 busiest wards ({names})", f"{conc['top_k_share_pct']}%", period="14 days", ref_id=_ref("concentration", names))
    add("total cases in scope", len(cases), unit="cases")
    add("open cases", open_n, unit="cases")
    return AnalyticsFactSet(scope_label=scope_label, facts=facts)
