"""Applies an authorized human triage decision (§51A.8) to the case. The AI recommendation / override audit lives in ``AIGateway.triage_decision``."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from backend.core.exceptions import CivicConnectException
from backend.models import CivicCase, Department
from backend.services.workflow import TRIAGEABLE, add_event, transition, utcnow


def apply_decision(db: Session, case: CivicCase, decision: dict[str, Any], actor_id: str, actor_role: str | None) -> CivicCase:
    if case.status not in TRIAGEABLE:
        raise CivicConnectException("INVALID_STATE", f"A case in state {case.status} cannot be triaged.", 409, {"status": case.status, "allowed": sorted(TRIAGEABLE)})
    dept = decision.get("department_id")
    if dept is not None and db.get(Department, dept) is None:
        raise CivicConnectException("DEPARTMENT_UNKNOWN", "Unknown department.", 422, {"department_id": dept})
    before = {"severity": case.severity, "priority": case.priority, "department_id": case.department_id, "sla_hours": case.sla_hours}
    case.severity, case.priority = decision["severity"], decision["priority"]
    case.department_id = dept or case.department_id
    case.sla_hours = int(decision["sla_hours"])
    case.sla_deadline = case.created_at + timedelta(hours=case.sla_hours)
    case.triaged_at = utcnow()
    add_event(db, case.id, "TRIAGE_DECIDED", actor_id=actor_id, actor_role=actor_role, visibility="INTERNAL",
              metadata={"before": before, "after": {"severity": case.severity, "priority": case.priority, "department_id": case.department_id, "sla_hours": case.sla_hours},
                        "overridden_fields": decision.get("overridden_fields", []), "reason": decision.get("reason")})
    if case.status in ("NEEDS_REVIEW", "REOPENED"):
        transition(db, case, "ASSIGNED", actor_id=actor_id, actor_role=actor_role, metadata={"department_id": case.department_id})
    db.flush()
    return case
