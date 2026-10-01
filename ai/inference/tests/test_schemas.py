import pytest
from pydantic import ValidationError

from ai.inference.schemas import (
    AIMetadata,
    CopilotQuery,
    CopilotScope,
    EvidenceInput,
    FusionSignals,
    IntakeProposal,
    IntakeRequest,
    IntakeResponse,
    Location,
    ResolutionReviewResponse,
    TriageRequest,
)


def meta():
    return AIMetadata(task_type="intake", source="rules")


def proposal(**kw):
    base = dict(title="t", description="d", category="roads", subcategory="pothole", severity="HIGH", language="en")
    return IntakeProposal(**{**base, **kw})


def test_intake_response_matches_51a5_contract_keys():
    r = IntakeResponse(proposal=proposal(location=Location(latitude=19.07, longitude=72.87)), confidence=0.9, ai_metadata=meta())
    d = r.model_dump(mode="json")
    assert {"proposal", "confidence", "warnings", "requires_confirmation"} <= set(d)
    assert {"title", "description", "category", "severity", "location", "language"} <= set(d["proposal"])
    assert d["requires_confirmation"] is True and d["proposal"]["severity"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def test_proposals_can_never_skip_confirmation():
    with pytest.raises(ValidationError):
        IntakeResponse(proposal=proposal(), confidence=0.5, requires_confirmation=False, ai_metadata=meta())


def test_confidence_and_severity_are_validated():
    with pytest.raises(ValidationError):
        IntakeResponse(proposal=proposal(), confidence=1.5, ai_metadata=meta())
    with pytest.raises(ValidationError):
        proposal(severity="SEVERE")


def test_intake_request_needs_some_input():
    with pytest.raises(ValidationError):
        IntakeRequest()
    with pytest.raises(ValidationError):
        IntakeRequest(text="   ")
    IntakeRequest(text="pothole")
    IntakeRequest(evidence=[EvidenceInput(evidence_id="e1", media_type="IMAGE", url="https://signed.example/x")])


def test_location_bounds():
    with pytest.raises(ValidationError):
        Location(latitude=91, longitude=0)
    with pytest.raises(ValidationError):
        Location(latitude=0, longitude=181)


def test_evidence_needs_payload_and_never_serialises_bytes():
    with pytest.raises(ValidationError):
        EvidenceInput(evidence_id="e", media_type="IMAGE")
    e = EvidenceInput(evidence_id="e", media_type="IMAGE", data=b"\xff\xd8SECRETBYTES", mime_type="image/jpeg")
    assert "SECRETBYTES" not in repr(e)
    assert "data" not in e.model_dump() and "SECRETBYTES" not in e.model_dump_json()


def test_requests_reject_unknown_and_sensitive_fields():
    with pytest.raises(ValidationError):
        TriageRequest(category="roads", reporter_religion="x")
    with pytest.raises(ValidationError):
        TriageRequest(category="roads", reporter_id="u1")
    with pytest.raises(ValidationError):
        IntakeRequest(text="x", user_role="admin")


def test_resolution_response_cannot_authorise_closure():
    kw = dict(consistency="CONSISTENT", unresolved_condition_suspected=False, recommend_verification_request=True,
              confidence=0.9, reasons=[], ai_metadata=meta())
    assert ResolutionReviewResponse(**kw).autonomous_closure_allowed is False
    with pytest.raises(ValidationError):
        ResolutionReviewResponse(**kw, autonomous_closure_allowed=True)


def test_fusion_signals_include_the_four_contract_keys():
    d = FusionSignals(semantic=0.5, geospatial=0.4, temporal=0.3).model_dump()
    assert {"semantic", "geospatial", "temporal", "visual"} <= set(d)


def test_copilot_scope_accepts_contract_field_names():
    q = CopilotQuery.model_validate({"query": "x", "scope": {"ward_id": "w1", "department_id": None, "from": "2026-09-01T00:00:00Z", "until": None}})
    assert q.scope.ward_id == "w1" and q.scope.from_ is not None
    with pytest.raises(ValidationError):
        CopilotScope(ward_id="w", sql="select *")


def test_json_round_trip():
    r = IntakeResponse(proposal=proposal(), confidence=0.7, ai_metadata=meta())
    assert IntakeResponse.model_validate_json(r.model_dump_json()) == r
