"""§51A.5 / 51A.7 / 51A.8 / 51A.15 request and response models, exactly as the frozen contract states them.

Additive fields (allowed by §51A.19) are marked ``# additive``; clients must ignore unknown response fields. Request models ignore unknown
keys so older/newer clients keep working. Department: ``department`` / ``suggested_department`` carry the department CODE exactly as the contract
example shows (``"WATER"``); the canonical taxonomy id (``water_supply``) rides in the additive ``department_id`` / ``suggested_department_id``.
``TriageDecisionRequest.department_id`` accepts either (the gateway canonicalises).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
Priority = Literal["LOW", "NORMAL", "HIGH", "URGENT"]


class _In(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class _Out(BaseModel):
    model_config = ConfigDict(extra="ignore")


class GeoPoint(_In):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0)


# ------------------------------------------------------------------ 51A.5 AI intake
class IntakeAnalyzeRequest(_In):
    text: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    language_hint: str | None = None
    location: GeoPoint | None = None


class IntakeProposalOut(_Out):
    title: str
    description: str
    category: str
    severity: Severity
    location: dict[str, Any] | None = None
    language: str
    subcategory: str | None = None                  # additive
    suggested_department: str | None = None         # additive (department code, e.g. "WATER")
    suggested_department_id: str | None = None      # additive (canonical id)
    transcript: str | None = None                   # additive
    reasons: list[str] = Field(default_factory=list)        # additive
    evidence_refs: list[str] = Field(default_factory=list)  # additive
    title_local: str | None = None                  # additive: title in the citizen's language when it is not English (presentation only; ``title`` stays canonical English)
    summary_local: str | None = None                # additive: short summary in the citizen's language
    local_language: str | None = None               # additive: language code of title_local / summary_local


class IntakeAnalyzeResponse(_Out):
    proposal: IntakeProposalOut
    confidence: float
    warnings: list[str] = Field(default_factory=list)
    requires_confirmation: Literal[True] = True
    alternatives: list[dict[str, Any]] = Field(default_factory=list)   # additive
    ai_metadata: dict[str, Any] | None = None                          # additive
    analysis_id: str | None = None                                     # additive
    image_analysis: list[dict[str, Any]] = Field(default_factory=list)  # additive: local road-damage detections per image (boxes in original pixels)


# ------------------------------------------------------------------ 51A.7 fusion
class FusionSignalsOut(_Out):
    semantic: float
    geospatial: float
    temporal: float
    visual: float
    category: float = 0.0                                                # additive
    signals_available: list[str] = Field(default_factory=list)          # additive


class FusionMatchOut(_Out):
    case_id: str
    similarity: float
    signals: FusionSignalsOut
    distance_m: float | None = None                                     # additive
    age_hours: float | None = None                                      # additive
    semantic_source: str | None = None                                  # additive


class FusionAnalyzeResponse(_Out):
    matches: list[FusionMatchOut]
    recommendation: Literal["POSSIBLE_DUPLICATE", "RELATED", "NO_MATCH"]
    warnings: list[str] = Field(default_factory=list)                   # additive
    ai_metadata: dict[str, Any] | None = None                           # additive
    analysis_id: str | None = None                                      # additive


# ------------------------------------------------------------------ 51A.8 triage
class TriageRecommendationOut(_Out):
    severity: Severity
    priority: Priority
    department: str | None                                              # department code, e.g. "WATER"
    sla_hours: int
    department_id: str | None = None                                    # additive (canonical taxonomy id)
    sla_class: str | None = None                                        # additive


class TriageAnalyzeResponse(_Out):
    recommendation: TriageRecommendationOut
    confidence: float
    reasons: list[str]
    warnings: list[str] = Field(default_factory=list)
    priority_score: int | None = None                                   # additive
    score_breakdown: list[dict[str, Any]] = Field(default_factory=list)  # additive
    ai_metadata: dict[str, Any] | None = None                           # additive
    analysis_id: str | None = None                                      # additive


class TriageDecisionRequest(_In):
    severity: Severity
    priority: Priority
    department_id: str
    sla_hours: int = Field(gt=0, le=24 * 365)
    reason: str = ""


class TriageDecisionResponse(_Out):
    case_id: str
    decision: TriageDecisionRequest
    ai_recommendation: TriageRecommendationOut | None = None
    overridden_fields: list[str] = Field(default_factory=list)
    overridden: bool = False
    decided_by: str
    recorded_at: datetime
    audit_event_emitted: bool = False


# ------------------------------------------------------------------ 51A.15 copilot
class CopilotScopeIn(_In):
    ward_id: str | None = None
    department_id: str | None = None
    from_: datetime | None = Field(default=None, alias="from")
    until: datetime | None = None


class CopilotQueryRequest(_In):
    query: str = Field(min_length=1, max_length=2000)
    scope: CopilotScopeIn = Field(default_factory=CopilotScopeIn)


class CitationOut(_Out):
    type: Literal["CASE", "ANALYTIC", "INCIDENT"]
    id: str


class CopilotQueryResponse(_Out):
    answer: str
    data: list[dict[str, Any]]
    citations: list[CitationOut]
    warnings: list[str] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)      # additive (audit)
    ai_metadata: dict[str, Any] | None = None                           # additive


# ------------------------------------------------------------------ AI-4 resolution review (INTERNAL hook: no §51A endpoint)
VerificationResult = Literal["YES", "PARTIAL", "STILL_OCCURRING", "NO"]


class ResolutionReviewIn(_In):
    """What the work-order ``complete`` (§51A.9) / citizen ``verification`` (§51A.10) handlers pass to the gateway."""

    notes: str | None = None
    resolution_evidence_ids: list[str] = Field(default_factory=list)
    citizen_verification: VerificationResult | None = None
    citizen_comment: str | None = None


class ResolutionReviewOut(_Out):
    """FLAGS ONLY. ``autonomous_closure_allowed`` is always False; closing/reopening stays an authorised human or policy transition."""

    consistency: Literal["CONSISTENT", "INCONSISTENT", "INSUFFICIENT_EVIDENCE"]
    unresolved_condition_suspected: bool
    recommend_verification_request: bool
    confidence: float
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    autonomous_closure_allowed: Literal[False] = False
    ai_metadata: dict[str, Any] | None = None
    analysis_id: str | None = None


# ------------------------------------------------------------------ AI-5 analytics explanation (ADDITIVE endpoint, not in §51A)
class AnalyticsScopeIn(_In):
    ward_id: str | None = None
    department_id: str | None = None


class AnalyticsExplainRequest(_In):
    scope: AnalyticsScopeIn = Field(default_factory=AnalyticsScopeIn)


class AnalyticsHighlightOut(_Out):
    text: str
    fact_ids: list[str]


class AnalyticsExplainResponse(_Out):
    """Numbers come from ``facts`` (deterministic); ``summary``/``highlights`` only explain them and are verified against them (``grounded``)."""

    summary: str
    highlights: list[AnalyticsHighlightOut]
    citations: list[CitationOut]
    facts: list[dict[str, Any]]
    grounded: bool
    warnings: list[str] = Field(default_factory=list)
    ai_metadata: dict[str, Any] | None = None
    analysis_id: str | None = None
