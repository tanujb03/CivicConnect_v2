import pytest
from pydantic import ValidationError

from ai.inference.errors import ProviderUnavailable
from ai.inference.providers.fake import FakeProvider
from ai.inference.resolution.service import ResolutionService
from ai.inference.schemas import EvidenceInput, ResolutionReviewRequest, ResolutionReviewResponse, W


def img(i):
    return EvidenceInput(evidence_id=i, media_type="IMAGE", data=b"x", mime_type="image/jpeg")


def req(**kw):
    base = dict(case_id="c1", category="roads", subcategory="pothole", description="pothole", original_evidence=[img("before")],
                resolution_evidence=[img("after")], field_notes="filled and compacted")
    return ResolutionReviewRequest(**{**base, **kw})


def ai(consistency="CONSISTENT", unresolved=False, conf=0.9, reasons=("looks fixed",)):
    return FakeProvider(structured={"resolution": {"consistency": consistency, "unresolved_condition_suspected": unresolved,
                                                   "confidence": conf, "reasons": list(reasons)}})


def codes(r):
    return [w.split(":")[0] for w in r.warnings]


def test_never_authorises_autonomous_closure():
    for provider in (None, ai("CONSISTENT")):
        r = ResolutionService(provider).review(req(citizen_verification="YES"))
        assert r.autonomous_closure_allowed is False
    with pytest.raises(ValidationError):
        ResolutionReviewResponse(consistency="CONSISTENT", unresolved_condition_suspected=False, recommend_verification_request=False,
                                 confidence=1, reasons=[], autonomous_closure_allowed=True, ai_metadata=r.ai_metadata)


def test_missing_after_photo_is_insufficient_evidence_and_requests_verification():
    r = ResolutionService(None).review(req(resolution_evidence=[], field_notes=None))
    assert r.consistency == "INSUFFICIENT_EVIDENCE" and r.recommend_verification_request
    assert any("No resolution photo" in x for x in r.reasons) and any("field notes" in x for x in r.reasons)


@pytest.mark.parametrize("verdict", ["STILL_OCCURRING", "NO"])
def test_citizen_negative_verification_always_flags_unresolved_even_if_ai_says_consistent(verdict):
    r = ResolutionService(ai("CONSISTENT", conf=0.99)).review(req(citizen_verification=verdict))
    assert r.unresolved_condition_suspected and r.consistency == "INCONSISTENT" and r.recommend_verification_request


def test_partial_verification_is_flagged():
    r = ResolutionService(None).review(req(citizen_verification="PARTIAL"))
    assert r.unresolved_condition_suspected


def test_ai_can_add_flags():
    r = ResolutionService(ai("INCONSISTENT", unresolved=True)).review(req())
    assert r.consistency == "INCONSISTENT" and r.unresolved_condition_suspected and any(x.startswith("AI:") for x in r.reasons)
    assert r.ai_metadata.source == "provider+rules" and r.confidence == 0.9


def test_ai_consistent_with_citizen_yes_is_the_only_all_clear():
    r = ResolutionService(ai("CONSISTENT")).review(req(citizen_verification="YES"))
    assert r.consistency == "CONSISTENT" and not r.unresolved_condition_suspected and not r.recommend_verification_request
    r2 = ResolutionService(ai("CONSISTENT")).review(req())
    assert r2.recommend_verification_request  # citizen has not verified yet


def test_before_and_after_images_are_sent_in_order():
    p = ai()
    ResolutionService(p).review(req(original_evidence=[img("b1"), img("b2")], resolution_evidence=[img("a1")]))
    parts = p.calls[0][1]["parts"]
    assert [x.evidence.evidence_id for x in parts if x.kind == "image"] == ["b1", "b2", "a1"]
    assert "2 image(s) are ORIGINAL" in parts[0].text


def test_low_confidence_ai_does_not_assert_consistency():
    r = ResolutionService(ai("CONSISTENT", conf=0.2)).review(req())
    assert r.consistency == "INSUFFICIENT_EVIDENCE" and W.LOW_CONFIDENCE in codes(r)


@pytest.mark.parametrize("script", [ProviderUnavailable("down"), {"consistency": "WEIRD", "unresolved_condition_suspected": False, "confidence": 1, "reasons": []}])
def test_provider_failures_leave_deterministic_flags(script):
    r = ResolutionService(FakeProvider(structured={"resolution": script})).review(req(citizen_verification="NO"))
    assert r.unresolved_condition_suspected and r.ai_metadata.degraded and r.consistency == "INCONSISTENT"


def test_unanalysed_images_are_disclosed_without_provider():
    r = ResolutionService(None).review(req())
    assert W.IMAGE_NOT_ANALYZED in codes(r) and r.consistency == "INSUFFICIENT_EVIDENCE" and r.recommend_verification_request
