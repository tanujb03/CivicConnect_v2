"""What the gateway needs from storage. Implement these with SQLAlchemy/PostGIS/pgvector/object storage; ``memory.py`` has demo-city versions."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from ai.inference.copilot.tools import ToolExecutor  # noqa: F401  (re-exported: the copilot's executor port is defined by the adapter)
from ai.inference.schemas import EvidenceInput


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


class CaseRepository(Protocol):
    def get_case(self, case_id: str) -> CaseSnapshot | None: ...

    def fusion_candidates(self, case: CaseSnapshot, *, radius_m: float, time_window_days: float, max_candidates: int, same_category: bool) -> list[CaseSnapshot]:
        """Candidate cases bounded by the policy (PostGIS ST_DWithin + time window + category; pgvector for embeddings), excluding ``case`` itself."""

    def save_triage_decision(self, case_id: str, decision: dict, actor_id: str) -> None: ...


class EvidenceResolver(Protocol):
    def resolve(self, evidence_id: str, actor_id: str) -> EvidenceInput | None:
        """evidence_id -> bytes / BACKEND-SIGNED url / transcript, or None when unknown or not visible to the actor. Never pass user-supplied URLs (SSRF)."""


class AIAnalysisStore(Protocol):
    def save(self, record: dict) -> str:
        """Persist an AIAnalysis row (design §34); returns its id."""

    def latest(self, case_id: str, task_type: str) -> dict | None: ...


class AuditSink(Protocol):
    def emit(self, *, actor_id: str, action: str, entity_type: str, entity_id: str, before: dict | None, after: dict | None) -> bool:
        """Write an AuditEvent; True when it was accepted."""
