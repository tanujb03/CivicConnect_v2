"""Deterministic severity baseline and priority/SLA computation (Section 36).

Everything here is pure and configuration-driven. AI may *recommend* a severity
(see ``service.py``); the priority score, priority and SLA are always computed
from these rules.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import Taxonomy
from ..local.featurizer import normalize_text
from ..schemas import ScoreComponent


@dataclass
class SeverityBaseline:
    severity: str
    reasons: list[str] = field(default_factory=list)
    tags: set[str] = field(default_factory=set)


def rule_severity(t: Taxonomy, rules: dict, category: str, subcategory: str | None,
                  text: str | None) -> SeverityBaseline:
    """Taxonomy base severity, bumped by multilingual keyword escalators."""
    sub = t.subcategories.get(subcategory or "")
    base = sub.base_severity if sub else "LOW"
    out = SeverityBaseline(severity=base)
    label = t.label("subcategory", sub.id) if sub else category
    out.reasons.append(f"Base severity {base} for '{label}' (taxonomy {t.version})")
    norm = normalize_text(text or "")
    rank = t.severity_rank[base]
    for esc in rules.get("severity_escalators", []):
        hit = next((p for p in esc["patterns"] if normalize_text(p) and normalize_text(p) in norm), None)
        if hit:
            rank += esc["bump"]
            out.reasons.append(f"{esc['reason']} (matched '{hit}')")
            if esc.get("tag"):
                out.tags.add(esc["tag"])
    out.severity = t.severity_by_rank(rank)
    return out


@dataclass
class PriorityResult:
    score: int
    priority: str
    sla_class: str
    sla_hours: int
    breakdown: list[ScoreComponent]


def _priority_for(rules: dict, score: int) -> str:
    for th in sorted(rules["priority_thresholds"], key=lambda x: -x["min_score"]):
        if score >= th["min_score"]:
            return th["priority"]
    return rules["priority_thresholds"][-1]["priority"]


def compute_priority(t: Taxonomy, rules: dict, *, severity: str, support_count: int = 0,
                     case_age_hours: float = 0.0, recurrence_count: int = 0,
                     location_tags: set[str] | list[str] = (), incident_active: bool = False) -> PriorityResult:
    mods = rules["modifiers"]
    comps: list[ScoreComponent] = [
        ScoreComponent(name="severity", points=rules["severity_score"][severity], reason=f"severity {severity}")
    ]

    def add(name: str, units: float, cfg: dict, label: str | None = None) -> None:
        pts = int(min(units * cfg["per_unit"], cfg["cap"])) if "per_unit" in cfg else 0
        if pts:
            comps.append(ScoreComponent(name=name, points=pts, reason=label or cfg["reason"]))

    add("support", support_count, mods["support_count"], f"{support_count} supporting citizen(s)")
    sens = [tg for tg in dict.fromkeys(location_tags) if tg in mods["location_sensitivity"]["tags"]]
    if sens:
        cfg = mods["location_sensitivity"]
        comps.append(ScoreComponent(name="location", points=min(len(sens) * cfg["per_tag"], cfg["cap"]),
                                    reason=f"sensitive location: {', '.join(sens)}"))
    add("age", int(case_age_hours // 24), mods["case_age_days"], f"case age {int(case_age_hours // 24)} day(s)")
    add("recurrence", recurrence_count, mods["recurrence_count"], f"{recurrence_count} recurrence(s)")
    if incident_active:
        comps.append(ScoreComponent(name="incident", points=mods["incident_active"]["bonus"],
                                    reason=mods["incident_active"]["reason"]))

    score = min(100, sum(c.points for c in comps))
    priority = _priority_for(rules, score)

    def sla_for(prio: str, sev: str) -> str:
        for o in rules.get("sla_overrides", []):
            if o["when_severity"] == sev:
                return o["sla_class"]
        return t.priority_sla_class[prio]

    sla_class = sla_for(priority, severity)
    # SLA-risk bonus: a case that has consumed most of its SLA moves up.
    risk = mods["sla_risk"]
    if case_age_hours >= risk["threshold_fraction"] * t.sla_hours[sla_class]:
        comps.append(ScoreComponent(name="sla_risk", points=risk["bonus"], reason=risk["reason"]))
        score = min(100, score + risk["bonus"])
        priority = _priority_for(rules, score)
        sla_class = sla_for(priority, severity)

    for fp in rules.get("force_priority", []):
        if fp["when_severity"] == severity and t.priority_rank[fp["priority"]] > t.priority_rank[priority]:
            priority = fp["priority"]
            comps.append(ScoreComponent(name="forced", points=0, reason=fp["reason"]))
            sla_class = sla_for(priority, severity)

    return PriorityResult(score=score, priority=priority, sla_class=sla_class,
                          sla_hours=t.sla_hours[sla_class], breakdown=comps)
