"""End-to-end smoke tests through the public AIService entry point (no network, no credentials)."""
import json
import logging

from ai.inference.schemas import (
    AnalyticsFact,
    AnalyticsFactSet,
    FusionCase,
    FusionRequest,
    IntakeRequest,
    ResolutionReviewRequest,
    TriageRequest,
    W,
)
from ai.inference.service import AIService

from .conftest import FIXTURE_ARTIFACT, NOW, POTHOLE_TEXT


def test_degraded_service_with_nothing_configured_never_raises():
    ai = AIService.from_env({})
    assert ai.analyze_intake(IntakeRequest(text="pothole")).requires_confirmation
    assert ai.analyze_triage(TriageRequest(category="roads", subcategory="pothole")).recommendation.priority
    assert ai.review_resolution(ResolutionReviewRequest(case_id="c", category="roads")).autonomous_closure_allowed is False
    assert ai.explain_analytics(AnalyticsFactSet(scope_label="s", facts=[AnalyticsFact(id="f", metric="m", value=1)])).grounded
    assert ai.analyze_fusion(FusionRequest(subject=FusionCase(case_id="s", category="roads", latitude=1, longitude=1, created_at=NOW))).recommendation == "NO_MATCH"


def test_service_loads_the_local_classifier_from_env_and_uses_it_as_fallback():
    ai = AIService.from_env({"AI_LOCAL_CLASSIFIER_PATH": str(FIXTURE_ARTIFACT)})
    r = ai.analyze_intake(IntakeRequest(text=POTHOLE_TEXT))
    assert r.proposal.category == "roads" and r.ai_metadata.source == "local_fallback"
    assert r.ai_metadata.model == "civic_text_b0_fixture" and r.ai_metadata.model_version == "fixture-1"


def test_fixture_requests_round_trip_through_the_service():
    cases = json.loads((FIXTURE_ARTIFACT / "golden.json").read_text(encoding="utf-8"))
    ai = AIService.from_env({"AI_LOCAL_CLASSIFIER_PATH": str(FIXTURE_ARTIFACT)})
    for g in cases:
        if not g["text"].strip():
            continue
        r = ai.analyze_intake(IntakeRequest(text=g["text"]))
        assert 0 <= r.confidence <= 1 and r.requires_confirmation and r.proposal.suggested_department in (None, *ai.taxonomy.departments)
        if not g["abstained"]:
            assert f"{r.proposal.category}/{r.proposal.subcategory}" == g["label_id"]


def test_bad_artifact_paths_degrade_instead_of_crashing(caplog):
    with caplog.at_level(logging.ERROR):
        ai = AIService.from_env({"AI_LOCAL_CLASSIFIER_PATH": "/nonexistent", "AI_FUSION_WEIGHTS_PATH": "/nonexistent/w.json"})
    assert ai.classifier is None and ai.fusion.weights.status == "uncalibrated_prior"
    assert ai.analyze_intake(IntakeRequest(text="x")).ai_metadata.source == "none"


def test_provider_is_built_from_env_without_network_and_secrets_stay_out_of_status():
    ai = AIService.from_env({"OPENAI_API_KEY": "sk-SUPER-SECRET", "AI_INTAKE_MODEL": "model-a", "AI_EMBEDDING_MODEL": "model-e"})
    st = ai.status()
    assert st["provider"]["name"] == "openai" and st["provider"]["models"]["intake"] == "model-a"
    assert "sk-SUPER-SECRET" not in json.dumps(st) and "sk-SUPER-SECRET" not in repr(ai.provider)
    assert st["taxonomy"]["status"] == "DRAFT_REQUIRES_REVIEW"


def test_key_without_models_degrades_visibly():
    ai = AIService.from_env({"OPENAI_API_KEY": "sk-x"})
    r = ai.analyze_intake(IntakeRequest(text="pothole"))
    assert r.ai_metadata.fallback_reason == "intake_model_not_configured" and any(w.startswith(W.PROVIDER_NOT_CONFIGURED) for w in r.warnings)


def test_every_response_carries_ai_metadata_with_versions():
    ai = AIService.from_env({"AI_LOCAL_CLASSIFIER_PATH": str(FIXTURE_ARTIFACT)})
    for md in (ai.analyze_intake(IntakeRequest(text=POTHOLE_TEXT)).ai_metadata,
               ai.analyze_triage(TriageRequest(category="roads", subcategory="pothole")).ai_metadata):
        assert md.task_type and md.schema_version == "ai-schemas/1" and md.taxonomy_version == "1.0.0-draft" and md.created_at
