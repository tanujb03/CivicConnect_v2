"""§51A.11 timeline: immutable, role-filtered, cursor-paginated."""
from __future__ import annotations

from sqlalchemy.orm import Session

from backend.core.pagination import clamp_limit, paginate
from backend.core.permissions import STAFF_ROLES
from backend.models import CaseEvent, User

CITIZEN_HIDDEN_KEYS = {"reason_internal", "overridden_fields", "analysis_id", "ai", "assignee_id", "priority", "severity"}


def events_for(db: Session, user: User, case_id: str, *, cursor: str | None = None, limit: int | None = None) -> tuple[list[CaseEvent], str | None]:
    q = db.query(CaseEvent).filter(CaseEvent.case_id == case_id)
    if user.role not in STAFF_ROLES:
        q = q.filter(CaseEvent.visibility == "PUBLIC")
    return paginate(q, [(CaseEvent.seq, False)], cursor, clamp_limit(limit, default=50), lambda e: [e.seq])


def serialize(e: CaseEvent, staff: bool = True) -> dict:
    meta = e.event_metadata or {}
    if not staff:
        meta = {k: v for k, v in meta.items() if k not in CITIZEN_HIDDEN_KEYS}
    return {"id": e.id, "event_type": e.event_type, "actor_id": e.actor_id if staff else None, "timestamp": e.created_at, "metadata": meta}
