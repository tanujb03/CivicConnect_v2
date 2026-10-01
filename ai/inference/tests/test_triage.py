import pytest

from ai.inference.config import load_taxonomy, load_triage_rules
from ai.inference.errors import ProviderUnavailable
from ai.inference.providers.fake import FakeProvider
from ai.inference.schemas import TriageRequest, W
from ai.inference.triage.rules import compute_priority, rule_severity
from ai.inference.triage.service import TriageService

T, R = load_taxonomy(), load_triage_rules()


def prio(**kw):
    return compute_priority(T, R, **{"severity": "MEDIUM", **kw})


def test_baseline_priority_table():
    p = prio()
    assert (p.score, p.priority, p.sla_class, p.sla_hours) == (30, "NORMAL", "STANDARD", 72)
    assert prio(severity="LOW").priority == "LOW" and prio(severity="LOW").sla_hours == 168
    assert prio(severity="HIGH").priority == "HIGH" and prio(severity="HIGH").sla_hours == 48


def test_critical_is_always_urgent_with_emergency_sla():
    p = prio(severity="CRITICAL")
    assert p.priority == "URGENT" and p.sla_class == "EMERGENCY" and p.sla_hours == 4


def test_documented_51a8_example_is_reproducible():
    # HIGH severity + 5 supporters + school location + 1 recurrence => URGENT / 24h
    p = prio(severity="HIGH", support_count=5, location_tags=["school"], recurrence_count=1)
    assert p.score == 80 and p.priority == "URGENT" and p.sla_hours == 24


def test_modifier_caps_are_respected():
    assert next(c for c in prio(support_count=1000).breakdown if c.name == "support").points == R["modifiers"]["support_count"]["cap"]
    assert next(c for c in prio(recurrence_count=99).breakdown if c.name == "recurrence").points == R["modifiers"]["recurrence_count"]["cap"]
    assert prio(severity="CRITICAL", support_count=1000, recurrence_count=99, incident_active=True,
                location_tags=["school", "hospital"], case_age_hours=24 * 400).score <= 100


def test_priority_is_monotonic_in_signals():
    order = {p: i for i, p in enumerate(["LOW", "NORMAL", "HIGH", "URGENT"])}
    last = -1
    for support in range(0, 30, 2):
        cur = order[prio(severity="MEDIUM", support_count=support, recurrence_count=support // 4).priority]
        assert cur >= last
        last = cur


def test_sla_risk_bonus_applies_when_most_of_the_sla_elapsed():
    fresh = prio(case_age_hours=1)
    aged = prio(case_age_hours=60)  # >= 75% of 72h
    assert "sla_risk" in [c.name for c in aged.breakdown] and "sla_risk" not in [c.name for c in fresh.breakdown]
    assert aged.score > fresh.score


def test_incident_context_raises_score():
    assert prio(incident_active=True).score == prio().score + 10


@pytest.mark.parametrize("text", ["pothole near the school", "गड्ढा स्कूल के पास", "शाळेजवळ खड्डा", "school ke paas gadda", "bachche gir rahe hain"])
def test_multilingual_escalators_bump_severity(text):
    assert rule_severity(T, R, "roads", "pothole", text).severity == "HIGH"


def test_escalators_are_capped_at_critical_and_report_reasons():
    b = rule_severity(T, R, "street_lighting", "exposed_live_wire", "wire sparking near school hospital accident")
    assert b.severity == "CRITICAL" and len(b.reasons) >= 2 and {"school", "hospital"} <= b.tags


def test_rules_only_service_output():
    r = TriageService().analyze(TriageRequest(category="water_supply", subcategory="pipe_leakage", text="leak", support_count=2))
    assert r.severity_source == "rules" and r.recommendation.department == "water_supply"
    assert r.confidence == R["rules_only_confidence"] and r.ai_metadata.confidence_basis == "rules_only_nominal"
    assert any(w.startswith(W.RULES_ONLY) for w in r.warnings) and r.reasons and r.score_breakdown
    assert r.ai_metadata.source == "rules" and r.ai_metadata.degraded


def ai_provider(sev="HIGH", conf=0.9, reasons=("R1",)):
    return FakeProvider(structured={"triage": {"severity": sev, "confidence": conf, "reasons": list(reasons)}})


def test_ai_severity_accepted_within_one_level():
    r = TriageService(ai_provider("HIGH")).analyze(TriageRequest(category="roads", subcategory="pothole", text="x"))
    assert r.severity_source == "ai" and r.recommendation.severity == "HIGH"
    assert any(x.startswith("AI:") for x in r.reasons) and r.ai_metadata.source == "provider+rules"
    assert r.confidence == 0.9 and not r.ai_metadata.degraded


def test_ai_cannot_set_priority_or_sla_directly():
    r1 = TriageService(ai_provider("HIGH")).analyze(TriageRequest(category="roads", subcategory="pothole", text="x"))
    r2 = TriageService().analyze(TriageRequest(category="roads", subcategory="pothole", text="x", ))
    # same deterministic pipeline: only the severity input differs
    assert r1.priority_score == 55 and r2.priority_score == 30


def test_large_divergence_keeps_rules_and_warns():
    r = TriageService(ai_provider("CRITICAL")).analyze(TriageRequest(category="roads", subcategory="damaged_footpath", text="x"))
    assert r.severity_source == "rules" and r.recommendation.severity == "LOW"
    assert any(w.startswith(W.AI_SEVERITY_DIVERGES) for w in r.warnings)


def test_low_confidence_ai_is_ignored():
    r = TriageService(ai_provider("HIGH", conf=0.2)).analyze(TriageRequest(category="roads", subcategory="pothole", text="x"))
    assert r.severity_source == "rules" and any(w.startswith(W.LOW_CONFIDENCE) for w in r.warnings)


def test_ai_cannot_lower_a_safety_critical_baseline():
    r = TriageService(ai_provider("HIGH")).analyze(TriageRequest(category="street_lighting", subcategory="exposed_live_wire", text="x"))
    assert r.recommendation.severity == "CRITICAL" and r.recommendation.priority == "URGENT"


@pytest.mark.parametrize("script", [ProviderUnavailable("down", status_code=503), {"severity": "BANANA", "confidence": 0.9, "reasons": []},
                                    {"nonsense": True}])
def test_provider_failures_degrade_to_rules_without_raising(script):
    r = TriageService(FakeProvider(structured={"triage": script})).analyze(TriageRequest(category="roads", subcategory="pothole", text="x"))
    assert r.severity_source == "rules" and r.ai_metadata.degraded and r.recommendation.priority == "NORMAL"


def test_model_not_configured_is_reported():
    p = FakeProvider(structured={"triage": {"severity": "HIGH", "confidence": 1, "reasons": []}}, models={"triage": ""})
    r = TriageService(p).analyze(TriageRequest(category="roads", subcategory="pothole"))
    assert r.severity_source == "rules" and not p.calls


def test_location_tags_from_text_feed_priority():
    base = TriageService().analyze(TriageRequest(category="roads", subcategory="pothole", text="pothole"))
    school = TriageService().analyze(TriageRequest(category="roads", subcategory="pothole", text="pothole near school"))
    assert school.priority_score > base.priority_score
    assert any(c.name == "location" for c in school.score_breakdown)
