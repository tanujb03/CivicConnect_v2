"""Deterministic severity / priority / SLA / department routing (design §36). Uses the AI package's pure rule functions, never a model."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ai.inference.config import load_taxonomy, load_triage_rules
from ai.inference.triage.rules import compute_priority, rule_severity


@lru_cache(maxsize=1)
def taxonomy():
    return load_taxonomy()


@lru_cache(maxsize=1)
def rules() -> dict:
    return load_triage_rules()


def resolve_category(category: str | None, subcategory: str | None) -> tuple[str, str | None]:
    """Valid taxonomy pair, or the explicit 'other / unclassified' bucket (a human triages it)."""
    t = taxonomy()
    cat = t.resolve_category(category) if category else None
    if cat is None:
        return "other", "unclassified" if "unclassified" in t.subcategories else None
    sub = subcategory if subcategory and t.is_valid_pair(cat, subcategory) else None
    return cat, sub


@dataclass
class Assessment:
    severity: str
    priority: str
    score: int
    sla_class: str
    sla_hours: int
    department_id: str | None


def assess(category: str, subcategory: str | None, text: str | None, *, support_count: int = 0, age_hours: float = 0.0, recurrence_count: int = 0,
           location_tags: list[str] | None = None, incident_active: bool = False) -> Assessment:
    t, r = taxonomy(), rules()
    base = rule_severity(t, r, category, subcategory, text)
    pr = compute_priority(t, r, severity=base.severity, support_count=support_count, case_age_hours=age_hours, recurrence_count=recurrence_count,
                          location_tags=set(location_tags or []) | base.tags, incident_active=incident_active)
    return Assessment(severity=base.severity, priority=pr.priority, score=pr.score, sla_class=pr.sla_class, sla_hours=pr.sla_hours,
                      department_id=t.department_for(category, subcategory))


def department_ids() -> list[str]:
    return sorted(taxonomy().departments)
