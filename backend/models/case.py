from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.session import Base
from backend.models.types import JSONType, UTCDateTime, new_id, utcnow


class CivicCase(Base):
    """Design §34 CivicCase. The server owns ``status``, ``priority`` (§36 rules), assignment and every timestamp."""

    __tablename__ = "civic_cases"
    __table_args__ = (
        UniqueConstraint("reporter_id", "client_case_id", name="uq_case_client_id"),
        Index("ix_case_dept_status", "department_id", "status"),
        Index("ix_case_geo", "latitude", "longitude"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)        # public id, e.g. CC-2026-000001
    client_case_id: Mapped[str | None] = mapped_column(String(64), nullable=True)            # offline-created id (dedupes retries)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)                     # canonical_description
    category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    subcategory: Mapped[str | None] = mapped_column(String(64), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(16), nullable=True)                  # LOW | MEDIUM | HIGH | CRITICAL
    priority: Mapped[str] = mapped_column(String(16), default="NORMAL", nullable=False)      # LOW | NORMAL | HIGH | URGENT | CRITICAL
    priority_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sla_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sla_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sla_deadline: Mapped[object | None] = mapped_column(UTCDateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="SUBMITTED", nullable=False, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_tags: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    ward_id: Mapped[str | None] = mapped_column(ForeignKey("wards.id"), nullable=True, index=True)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    reporter_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="CITIZEN", nullable=False)
    observed_at: Mapped[object | None] = mapped_column(UTCDateTime, nullable=True)
    support_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recurrence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reopen_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False, index=True)
    updated_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False)
    triaged_at: Mapped[object | None] = mapped_column(UTCDateTime, nullable=True)
    closed_at: Mapped[object | None] = mapped_column(UTCDateTime, nullable=True)


class CaseCounter(Base):
    """One row per year; locked while a ``case_number`` is allocated."""

    __tablename__ = "case_counters"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
