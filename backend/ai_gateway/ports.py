"""What the gateway needs from storage. Implement these with SQLAlchemy/PostGIS/pgvector/object storage; ``memory.py`` has demo-city versions."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from ai.inference.copilot.tools import ToolExecutor  # noqa: F401  (re-exported: the copilot's executor port is defined by the adapter)
from ai.inference.schemas import AnalyticsFactSet, EvidenceInput


@dataclass
class CaseSnapshot:
    """Everything the AI services need to know about a case. Contains NO reporter attributes except the id used for ownership checks."""

    id: str
    category: str
    subcategory: str | None
    text: str | None
    latitude: float
    longitude: float
    created_at: datetime
    status: str | None = None
    support_count: int = 0
    recurrence_count: int = 0
    location_tags: list[str] = field(default_factory=list)
    incident_active: bool = False
    reporter_id: str | None = None
    department_id: str | None = None
    embedding: list[float] | None = None
    embedding_model: str | None = None
    evidence_ids: list[str] = field(default_factory=list)   # ORIGINAL (before) evidence of the case


class CaseRepository(Protocol):
    def get_case(self, case_id: str) -> CaseSnapshot | None: ...

    def fusion_candidates(self, case: CaseSnapshot, *, radius_m: float, time_window_days: float, max_candidates: int, same_category: bool) -> list[CaseSnapshot]:
        """Candidate cases bounded by the policy (PostGIS ST_DWithin + time window + category; pgvector for embeddings), excluding ``case`` itself."""

    def save_triage_decision(self, case_id: str, decision: dict, actor_id: str) -> None: ...

    # Optional, like the evidence methods above (used by the ``embed`` job and by candidate search):
    def save_embedding(self, case_id: str, vector: list[float], model: str) -> dict:
        """Store the case's embedding: the JSON vector everywhere, plus the pgvector columns (embedding_vec, embedding_dim, embedding_model) where they exist.
        Returns ``{"dim": int, "model": str, "pgvector": bool}``."""


class EvidenceResolver(Protocol):
    def resolve(self, evidence_id: str, actor_id: str) -> EvidenceInput | None:
        """evidence_id -> bytes / BACKEND-SIGNED url / transcript, or None when unknown or not visible to the actor. Never pass user-supplied URLs (SSRF)."""

    # Optional (the gateway checks with getattr, so a resolver without them still works; the transcript is then simply not persisted / no audio job runs):
    def pending_audio(self, case_id: str) -> list[str]:
        """Ids of the case's READY report AUDIO evidence that has no transcript yet."""

    def save_transcript(self, evidence_id: str, text: str, language: str | None) -> None:
        """Store the transcript on the evidence item (only when it has none)."""


class AIAnalysisStore(Protocol):
    def save(self, record: dict) -> str:
        """Persist an AIAnalysis row (design §34); returns its id."""

    def latest(self, case_id: str, task_type: str) -> dict | None: ...


class AuditSink(Protocol):
    def emit(self, *, actor_id: str, action: str, entity_type: str, entity_id: str, before: dict | None, after: dict | None) -> bool:
        """Write an AuditEvent; True when it was accepted."""


class AnalyticsFactSource(Protocol):
    def facts(self, *, actor_id: str, role: str, ward_id: str | None, department_id: str | None) -> AnalyticsFactSet:
        """DETERMINISTIC, role-scoped, display-ready facts (SQL aggregation in production; see ``ai/evaluation/analytics_facts.py`` for the spec).
        Raise ``ToolPermissionDenied`` when the actor may not see the requested scope."""


class ImageAnalyzer(Protocol):
    def analyze(self, evidence: EvidenceInput):
        """Local image model (e.g. the road-damage detector): ``ImageAnalysis`` (see ``vision.py``) or None when the evidence is not an analysable image."""
