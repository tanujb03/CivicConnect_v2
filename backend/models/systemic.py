from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.session import Base
from backend.models.types import JSONType, UTCDateTime, new_id, utcnow


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notif_user_created", "user_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(48), nullable=False)       # CASE_ASSIGNED | CASE_UPDATED | VERIFICATION_REQUESTED | CASE_RESOLVED | INCIDENT_CREATED | WORK_ORDER_ASSIGNED (§53)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    read_at: Mapped[object | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    # Expo push delivery of this notification (§53); values: PUSH_STATUSES. NONE = no push was requested for it.
    push_status: Mapped[str] = mapped_column(String(16), default="NONE", server_default="NONE", nullable=False)
    push_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    pushed_at: Mapped[object | None] = mapped_column(UTCDateTime, nullable=True)
    push_receipt_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


PUSH_STATUSES = ("NONE", "PENDING", "SENT", "FAILED", "SKIPPED")


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    geometry: Mapped[dict | None] = mapped_column(JSONType, nullable=True)            # GeoJSON boundary
    center_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    center_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    ward_id: Mapped[str | None] = mapped_column(ForeignKey("wards.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", nullable=False)   # ACTIVE | ENDED
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    ended_at: Mapped[object | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False)


class IncidentCase(Base):
    __tablename__ = "incident_cases"

    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("civic_cases.id"), primary_key=True)
    added_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    added_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False)


class AuditEvent(Base):
    """Append-only from the application's point of view (design §46)."""

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    before_json: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False)


class CaseEvent(Base):
    """Immutable case timeline (§51A.11). ``seq`` is the sync cursor (§51A.16 ``/sync/changes``)."""

    __tablename__ = "case_events"
    __table_args__ = (Index("ix_case_events_case", "case_id", "seq"),)

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(36), unique=True, default=new_id, nullable=False)
    case_id: Mapped[str] = mapped_column(ForeignKey("civic_cases.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    visibility: Mapped[str] = mapped_column(String(10), default="PUBLIC", nullable=False)   # PUBLIC (citizen may see) | INTERNAL (staff only)
    event_metadata: Mapped[dict] = mapped_column("metadata", JSONType, default=dict, nullable=False)
    created_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
