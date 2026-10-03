from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.session import Base
from backend.models.types import JSONType, UTCDateTime, new_id, utcnow


class ReportSignal(Base):
    __tablename__ = "report_signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("civic_cases.id"), nullable=True, index=True)
    reporter_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    original_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), default="SMARTPHONE", nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False)


class EvidenceItem(Base):
    """Metadata only: media bytes live in object storage (design §31, §44), never in PostgreSQL."""

    __tablename__ = "evidence_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("civic_cases.id"), nullable=True, index=True)
    uploader_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    work_order_id: Mapped[str | None] = mapped_column(ForeignKey("work_orders.id", use_alter=True, name="fk_evidence_work_order"), nullable=True, index=True)
    verification_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    purpose: Mapped[str] = mapped_column(String(16), default="REPORT", nullable=False)     # REPORT | RESOLUTION | VERIFICATION
    object_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    filename: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    media_type: Mapped[str] = mapped_column(String(16), nullable=False)                    # IMAGE | AUDIO | VIDEO
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)                        # declared by the client, verified on completion
    status: Mapped[str] = mapped_column(String(16), default="PENDING", nullable=False)     # PENDING | READY | REJECTED
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    captured_at: Mapped[object | None] = mapped_column(UTCDateTime, nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    uploaded_at: Mapped[object | None] = mapped_column(UTCDateTime, nullable=True)


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("civic_cases.id"), nullable=True, index=True)
    report_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)       # intake | fusion | triage | resolution | copilot | analytics_explain
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    schema_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    degraded: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    result_json: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    extra: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    created_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False)


class CaseEmbedding(Base):
    """Cached text embedding of a case (AI-2). ``vector`` is a JSON list so this works everywhere; a pgvector column/index can replace it later."""

    __tablename__ = "case_embeddings"

    case_id: Mapped[str] = mapped_column(ForeignKey("civic_cases.id"), primary_key=True)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    vector: Mapped[list] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False)


class CaseRelation(Base):
    __tablename__ = "case_relations"
    __table_args__ = (UniqueConstraint("case_a", "case_b", "relation_type", name="uq_case_relation"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_a: Mapped[str] = mapped_column(ForeignKey("civic_cases.id"), nullable=False, index=True)
    case_b: Mapped[str] = mapped_column(ForeignKey("civic_cases.id"), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(32), default="POSSIBLE_DUPLICATE", nullable=False)   # POSSIBLE_DUPLICATE | RELATED | MERGED_INTO
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False)


class Support(Base):
    """A citizen backing a case (``SUPPORTER``) or contributing to it (``CONTRIBUTOR``, §51A.4)."""

    __tablename__ = "supports"
    __table_args__ = (UniqueConstraint("case_id", "user_id", name="uq_support"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("civic_cases.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), default="SUPPORTER", nullable=False)
    created_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False)


class WorkOrder(Base):
    __tablename__ = "work_orders"
    __table_args__ = (Index("ix_wo_worker_status", "assigned_worker_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("civic_cases.id"), nullable=False, index=True)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    assigned_worker_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority: Mapped[str] = mapped_column(String(16), default="NORMAL", nullable=False)
    deadline: Mapped[object | None] = mapped_column(UTCDateTime, nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)                         # completion notes
    status: Mapped[str] = mapped_column(String(16), default="ASSIGNED", nullable=False, index=True)   # ASSIGNED | IN_PROGRESS | COMPLETED | CANCELLED
    started_at: Mapped[object | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False)
    completed_at: Mapped[object | None] = mapped_column(UTCDateTime, nullable=True)


class Verification(Base):
    __tablename__ = "verifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("civic_cases.id"), nullable=False, index=True)
    citizen_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    result: Mapped[str] = mapped_column(String(24), nullable=False)                        # YES | PARTIAL | STILL_OCCURRING | NO
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
