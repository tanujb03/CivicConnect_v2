"""Pydantic schemas for every AI capability.

Response shapes mirror the frozen API contract (system design Section 51A.5,
51A.7, 51A.8, 51A.15). Where the contract is silent, fields are *additive*
(Section 51A.19: clients must ignore unknown response fields).

Request models use ``extra="forbid"``: unknown or sensitive attributes (e.g.
reporter identity) are rejected rather than silently ignored, which keeps
protected attributes out of triage (Section 13).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "ai-schemas/1"

Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
Priority = Literal["LOW", "NORMAL", "HIGH", "URGENT"]
SlaClass = Literal["EMERGENCY", "URGENT", "EXPEDITED", "STANDARD", "ROUTINE"]
MediaType = Literal["IMAGE", "AUDIO", "VIDEO"]
VerificationResult = Literal["YES", "PARTIAL", "STILL_OCCURRING", "NO"]
FusionRecommendation = Literal["POSSIBLE_DUPLICATE", "RELATED", "NO_MATCH"]
ResolutionConsistency = Literal["CONSISTENT", "INCONSISTENT", "INSUFFICIENT_EVIDENCE"]
MetaSource = Literal["provider", "local_fallback", "rules", "provider+rules", "none"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Warning codes (machine-readable prefix, human-readable remainder)
# --------------------------------------------------------------------------- #
class W:
    PROVIDER_NOT_CONFIGURED = "PROVIDER_NOT_CONFIGURED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_OUTPUT_INVALID = "PROVIDER_OUTPUT_INVALID"
    LOCAL_FALLBACK_USED = "LOCAL_FALLBACK_USED"
    LOCAL_CLASSIFIER_DISAGREES = "LOCAL_CLASSIFIER_DISAGREES"
    NO_AI_AVAILABLE = "NO_AI_AVAILABLE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    IMAGE_NOT_ANALYZED = "IMAGE_NOT_ANALYZED"
    AUDIO_NOT_TRANSCRIBED = "AUDIO_NOT_TRANSCRIBED"
    TAXONOMY_REPAIRED = "TAXONOMY_REPAIRED"
    FUSION_UNCALIBRATED_PRIOR = "FUSION_UNCALIBRATED_PRIOR"
    FUSION_LEXICAL_ONLY = "FUSION_LEXICAL_ONLY"
    FUSION_CANDIDATE_OUT_OF_POLICY = "FUSION_CANDIDATE_OUT_OF_POLICY"
    RULES_ONLY = "RULES_ONLY"
    AI_SEVERITY_DIVERGES = "AI_SEVERITY_DIVERGES"
    EXPLANATION_UNGROUNDED_FALLBACK = "EXPLANATION_UNGROUNDED_FALLBACK"
    SCOPE_OVERRIDDEN = "SCOPE_OVERRIDDEN"
    TOOL_CALL_REJECTED = "TOOL_CALL_REJECTED"
    TOOL_EXECUTION_FAILED = "TOOL_EXECUTION_FAILED"
    CITATION_DROPPED = "CITATION_DROPPED"
    RESULT_TRUNCATED = "RESULT_TRUNCATED"
    COPILOT_UNAVAILABLE = "COPILOT_UNAVAILABLE"

    @staticmethod
    def make(code: str, message: str) -> str:
        return f"{code}: {message}"


# --------------------------------------------------------------------------- #
# Shared
# --------------------------------------------------------------------------- #
class Location(_Strict):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0)


class EvidenceInput(_Strict):
    """Evidence already resolved by the backend (bytes / signed URL / transcript).

    The adapter never fetches evidence by ID and never touches the database.
    ``data`` is excluded from serialisation and repr so media bytes cannot leak
    into logs or persisted AI metadata.
    """

    evidence_id: str
    media_type: MediaType
    mime_type: str | None = None
    data: bytes | None = Field(default=None, exclude=True, repr=False)
    url: str | None = Field(default=None, repr=False)
    transcript: str | None = None
    captured_at: datetime | None = None

    @model_validator(mode="after")
    def _has_payload(self) -> "EvidenceInput":
        if self.data is None and not self.url and not self.transcript:
            raise ValueError("evidence needs at least one of data, url or transcript")
        return self


class AIMetadata(_Strict):
    """Persisted alongside every recommendation (system design Section 12)."""

    task_type: str
    source: MetaSource
    provider: str | None = None
    model: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    schema_version: str = SCHEMA_VERSION
    taxonomy_version: str | None = None
    confidence_basis: str | None = None
    degraded: bool = False
    fallback_reason: str | None = None
    latency_ms: int | None = None
    created_at: datetime = Field(default_factory=utcnow)
    input_refs: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# AI-1 Intake  (51A.5)
# --------------------------------------------------------------------------- #
class IntakeRequest(_Strict):
    text: str | None = None
    evidence: list[EvidenceInput] = Field(default_factory=list)
    language_hint: str | None = None
    location: Location | None = None

    @model_validator(mode="after")
    def _has_input(self) -> "IntakeRequest":
        if not (self.text and self.text.strip()) and not self.evidence:
            raise ValueError("intake needs text or at least one evidence item")
        return self


class IntakeProposal(_Strict):
    title: str
    description: str
    category: str
    subcategory: str | None = None
    severity: Severity
    suggested_department: str | None = None
    location: Location | None = None
    language: str
    transcript: str | None = None
    reasons: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class IntakeAlternative(_Strict):
    category: str
    subcategory: str
    probability: float = Field(ge=0, le=1)


class IntakeResponse(_Strict):
    proposal: IntakeProposal
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
    requires_confirmation: Literal[True] = True
    alternatives: list[IntakeAlternative] = Field(default_factory=list)
    ai_metadata: AIMetadata


# --------------------------------------------------------------------------- #
# AI-2 Fusion  (51A.7)
# --------------------------------------------------------------------------- #
class FusionCase(_Strict):
    case_id: str
    category: str
    subcategory: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    created_at: datetime
    text: str | None = None
    embedding: list[float] | None = Field(default=None, repr=False)
    status: str | None = None


class FusionRequest(_Strict):
    subject: FusionCase
    candidates: list[FusionCase] = Field(default_factory=list)
    embedding_model: str | None = None  # model that produced the supplied embeddings


class FusionSignals(_Strict):
    semantic: float = Field(ge=0, le=1)
    geospatial: float = Field(ge=0, le=1)
    temporal: float = Field(ge=0, le=1)
    visual: float = Field(default=0.0, ge=0, le=1)  # 0.0 = not computed (see signals_available)
    category: float = Field(default=0.0, ge=0, le=1)
    signals_available: list[str] = Field(default_factory=list)


class FusionMatch(_Strict):
    case_id: str
    similarity: float = Field(ge=0, le=1)
    signals: FusionSignals
    distance_m: float
    age_hours: float
    semantic_source: Literal["embedding", "lexical"]


class FusionResponse(_Strict):
    matches: list[FusionMatch]
    recommendation: FusionRecommendation
    warnings: list[str] = Field(default_factory=list)
    ai_metadata: AIMetadata


# --------------------------------------------------------------------------- #
# AI-3 Triage  (51A.8)
# --------------------------------------------------------------------------- #
class TriageRequest(_Strict):
    case_id: str | None = None
    category: str
    subcategory: str | None = None
    text: str | None = None
    support_count: int = Field(default=0, ge=0)
    case_age_hours: float = Field(default=0.0, ge=0)
    recurrence_count: int = Field(default=0, ge=0)
    location_tags: list[str] = Field(default_factory=list)
    incident_active: bool = False
    category_confidence: float | None = Field(default=None, ge=0, le=1)


class TriageRecommendation(_Strict):
    severity: Severity
    priority: Priority
    department: str | None
    sla_hours: int
    sla_class: SlaClass


class ScoreComponent(_Strict):
    name: str
    points: int
    reason: str


class TriageResponse(_Strict):
    recommendation: TriageRecommendation
    confidence: float = Field(ge=0, le=1)
    reasons: list[str]
    warnings: list[str] = Field(default_factory=list)
    priority_score: int
    score_breakdown: list[ScoreComponent]
    severity_source: Literal["ai", "rules"]
    ai_metadata: AIMetadata


# --------------------------------------------------------------------------- #
# AI-4 Resolution intelligence
# --------------------------------------------------------------------------- #
class ResolutionReviewRequest(_Strict):
    case_id: str
    category: str
    subcategory: str | None = None
    description: str | None = None
    original_evidence: list[EvidenceInput] = Field(default_factory=list)
    resolution_evidence: list[EvidenceInput] = Field(default_factory=list)
    field_notes: str | None = None
    citizen_verification: VerificationResult | None = None
    citizen_comment: str | None = None


class ResolutionReviewResponse(_Strict):
    """Flag-only output. ``autonomous_closure_allowed`` is a constant False."""

    consistency: ResolutionConsistency
    unresolved_condition_suspected: bool
    recommend_verification_request: bool
    confidence: float = Field(ge=0, le=1)
    reasons: list[str]
    warnings: list[str] = Field(default_factory=list)
    autonomous_closure_allowed: Literal[False] = False
    ai_metadata: AIMetadata


# --------------------------------------------------------------------------- #
# AI-5 Analytics explanation
# --------------------------------------------------------------------------- #
class AnalyticsFact(_Strict):
    """One deterministic fact produced by backend aggregation (never by a model)."""

    id: str
    metric: str
    value: float | int | str
    unit: str | None = None
    period: str | None = None
    ref_type: Literal["CASE", "ANALYTIC", "INCIDENT"] = "ANALYTIC"
    ref_id: str | None = None


class AnalyticsFactSet(_Strict):
    scope_label: str
    facts: list[AnalyticsFact] = Field(min_length=1)


class AnalyticsHighlight(_Strict):
    text: str
    fact_ids: list[str]


class Citation(_Strict):
    type: Literal["CASE", "ANALYTIC", "INCIDENT"]
    id: str


class AnalyticsExplanation(_Strict):
    summary: str
    highlights: list[AnalyticsHighlight]
    citations: list[Citation]
    grounded: bool
    warnings: list[str] = Field(default_factory=list)
    ai_metadata: AIMetadata


# --------------------------------------------------------------------------- #
# AI-6 Copilot  (51A.15)
# --------------------------------------------------------------------------- #
class CopilotScope(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    ward_id: str | None = None
    department_id: str | None = None
    from_: datetime | None = Field(default=None, alias="from")
    until: datetime | None = None


class CopilotQuery(_Strict):
    query: str
    scope: CopilotScope = Field(default_factory=CopilotScope)


class ActorContext(_Strict):
    """Authenticated actor, supplied by the backend (never by the client/model)."""

    user_id: str
    role: str


class ExecutedToolCall(_Strict):
    tool: str
    arguments: dict[str, Any]
    row_count: int
    truncated: bool = False


class CopilotResponse(_Strict):
    answer: str
    data: list[dict[str, Any]]
    citations: list[Citation]
    warnings: list[str] = Field(default_factory=list)
    tool_calls: list[ExecutedToolCall] = Field(default_factory=list)
    ai_metadata: AIMetadata
