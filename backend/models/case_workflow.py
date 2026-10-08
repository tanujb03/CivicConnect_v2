from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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
    __table_args__ = (Index("ix_evidence_scan_status", "scan_status"),)                     # the scan worker and the quarantine gate filter on it

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
    # malware scan (design §44): new rows start PENDING; rows that existed before migration 0003 were backfilled UNSCANNED. Values: SCAN_STATUSES.
    scan_status: Mapped[str] = mapped_column(String(16), default="PENDING", server_default="PENDING", nullable=False)
    scan_engine: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scan_signature: Mapped[str | None] = mapped_column(String(200), nullable=True)           # signature / threat name when INFECTED
    scanned_at: Mapped[object | None] = mapped_column(UTCDateTime, nullable=True)


SCAN_STATUSES = ("PENDING", "CLEAN", "INFECTED", "UNSCANNED", "ERROR")


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
    """Cached text embedding of a case (AI-2). ``vector`` is a JSON list so this works everywhere (SQLite, no extension).

    On PostgreSQL with pgvector, migration 0003 also adds ``embedding_vec vector`` (NO fixed dimension: the final model, e5-small = 384 or e5-base = 768, is not
    decided yet) and partial HNSW cosine indexes for 384 and 768 dims. That column and its indexes are deliberately NOT mapped here (like ``civic_cases.geog``):
    they do not exist on SQLite or on a PostgreSQL without the extension, so they are read and written with SQL (see alembic/versions/0003_*.py for the query form).
    ``embedding_dim`` / ``embedding_model`` describe whichever vector a row holds and are plain columns everywhere (``model`` is the older, required name column).
    """

    __tablename__ = "case_embeddings"

    case_id: Mapped[str] = mapped_column(ForeignKey("civic_cases.id"), primary_key=True)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    vector: Mapped[list] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    embedding_dim: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(Text, nullable=True)


FLAG_KINDS = ("STILL_EXISTS", "OUTDATED", "INCORRECT", "INAPPROPRIATE")
FLAG_STATUSES = ("OPEN", "UPHELD", "DISMISSED")


class CaseFlag(Base):
    """A citizen's flag on a case: it still exists, is outdated, wrong or inappropriate. One flag per (case, user, kind); staff resolve it (UPHELD / DISMISSED)."""

    __tablename__ = "case_flags"
    __table_args__ = (
        UniqueConstraint("case_id", "user_id", "kind", name="uq_case_flag"),
        CheckConstraint("kind IN ('STILL_EXISTS', 'OUTDATED', 'INCORRECT', 'INAPPROPRIATE')", name="ck_case_flags_kind"),
        CheckConstraint("status IN ('OPEN', 'UPHELD', 'DISMISSED')", name="ck_case_flags_status"),
        Index("ix_case_flags_case_kind", "case_id", "kind"),
        Index("ix_case_flags_status", "status"),
        Index("ix_case_flags_case_status", "case_id", "status"),                            # "open flags of a case" (review threshold)
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("civic_cases.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)                          # FLAG_KINDS
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", server_default="OPEN", nullable=False)   # FLAG_STATUSES
    resolved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[object | None] = mapped_column(UTCDateTime, nullable=True)


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
