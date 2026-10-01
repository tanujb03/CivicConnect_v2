import pytest

from ai.inference.analytics.service import AnalyticsExplainer
from ai.inference.errors import ProviderUnavailable
from ai.inference.grounding import allowed_numbers, numeric_tokens, ungrounded_numbers
from ai.inference.providers.fake import FakeProvider
from ai.inference.schemas import AnalyticsFact, AnalyticsFactSet, W

FACTS = AnalyticsFactSet(scope_label="Ward 18 sanitation", facts=[
    AnalyticsFact(id="f1", metric="cases in last 7 days", value=31, period="7 days", ref_type="ANALYTIC", ref_id="an-1"),
    AnalyticsFact(id="f2", metric="cases within 800 m", value=19, unit="cases", ref_id="an-2"),
    AnalyticsFact(id="f3", metric="above previous 30-day baseline", value="27%", ref_type="ANALYTIC", ref_id="an-3"),
])


def prov(summary, highlights):
    return FakeProvider(structured={"analytics": {"summary": summary, "highlights": highlights}})


def codes(r):
    return [w.split(":")[0] for w in r.warnings]


def test_grounded_model_explanation_is_accepted():
    p = prov("Ward 18 sanitation saw 31 cases in 7 days, 27% above baseline.",
             [{"text": "19 cases cluster within 800 m", "fact_ids": ["f2"]}, {"text": "31 cases in 7 days", "fact_ids": ["f1"]}])
    r = AnalyticsExplainer(p).explain(FACTS)
    assert r.grounded and r.ai_metadata.source == "provider" and r.warnings == []
    assert {c.id for c in r.citations} == {"an-1", "an-2"} and r.ai_metadata.input_refs == ["f1", "f2", "f3"]


def test_fabricated_numbers_are_rejected_and_replaced_by_a_template():
    p = prov("Cases rose by 45% in 7 days.", [{"text": "45% rise", "fact_ids": ["f1"]}])
    r = AnalyticsExplainer(p).explain(FACTS)
    assert W.EXPLANATION_UNGROUNDED_FALLBACK in codes(r) and r.ai_metadata.source == "rules" and "45" not in r.summary
    assert "31" in r.summary and r.ai_metadata.degraded


def test_unknown_or_missing_fact_ids_are_rejected():
    for ids in (["f99"], []):
        r = AnalyticsExplainer(prov("31 cases", [{"text": "31", "fact_ids": ids}])).explain(FACTS)
        assert r.ai_metadata.source == "rules"


def test_no_provider_or_failure_uses_deterministic_template():
    for prv in (None, FakeProvider(structured={"analytics": ProviderUnavailable("down")})):
        r = AnalyticsExplainer(prv).explain(FACTS)
        assert r.ai_metadata.source == "rules" and r.grounded and len(r.highlights) == 3 and "Ward 18 sanitation" in r.summary


def test_duplicate_fact_ids_are_invalid_input():
    dup = AnalyticsFactSet(scope_label="x", facts=[AnalyticsFact(id="a", metric="m", value=1), AnalyticsFact(id="a", metric="n", value=2)])
    with pytest.raises(ValueError):
        AnalyticsExplainer().explain(dup)


def test_number_grounding_normalisation():
    assert numeric_tokens("1,234 cases and 12.50%") >= {"1234", "12.5", "12"}
    assert numeric_tokens("३१ केसेस") == {"31"}  # Devanagari digits
    assert numeric_tokens("007") == {"7"}
    allowed = allowed_numbers([1234, "27%", "7 days"])
    assert ungrounded_numbers("1,234 cases, 27% in 7 days", allowed) == set()
    assert ungrounded_numbers("28% in 7 days", allowed) == {"28"}


def test_devanagari_digits_in_model_text_are_grounded():
    r = AnalyticsExplainer(prov("३१ cases in 7 days", [{"text": "३१", "fact_ids": ["f1"]}])).explain(FACTS)
    assert r.ai_metadata.source == "provider"
