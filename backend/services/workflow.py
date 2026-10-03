"""Civic case state machine (design §35) and the timeline/audit side effects of every transition.

Every status change goes through ``transition``: it checks the table below, stamps the case, appends an immutable ``CaseEvent`` (the §51A.11 timeline), writes an
``AuditEvent`` for the actions §46 makes mandatory and notifies the reporter (§53). Nothing else may assign ``case.status``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.core.exceptions import CivicConnectException
from backend.models import CaseEvent, CivicCase
from backend.services.audit import record_audit
from backend.services.notifications import notify

STATES = ["SUBMITTED", "AI_PROCESSING", "NEEDS_REVIEW", "ASSIGNED", "WORK_ORDER_CREATED", "IN_PROGRESS", "RESOLUTION_SUBMITTED", "AWAITING_VERIFICATION",
          "VERIFIED", "REOPENED", "RESOLVED", "REJECTED"]

TRANSITIONS: dict[str, frozenset[str]] = {
    "SUBMITTED": frozenset({"AI_PROCESSING", "REJECTED"}),
    "AI_PROCESSING": frozenset({"NEEDS_REVIEW", "REJECTED"}),
    "NEEDS_REVIEW": frozenset({"ASSIGNED", "REJECTED"}),
    "ASSIGNED": frozenset({"WORK_ORDER_CREATED", "REJECTED"}),
    "WORK_ORDER_CREATED": frozenset({"IN_PROGRESS", "ASSIGNED", "REJECTED"}),           # back to ASSIGNED when a work order is cancelled
    "IN_PROGRESS": frozenset({"RESOLUTION_SUBMITTED", "ASSIGNED"}),
    "RESOLUTION_SUBMITTED": frozenset({"AWAITING_VERIFICATION"}),
    "AWAITING_VERIFICATION": frozenset({"VERIFIED", "REOPENED"}),
    "VERIFIED": frozenset({"RESOLVED"}),
    "REOPENED": frozenset({"ASSIGNED", "WORK_ORDER_CREATED", "REJECTED"}),
    "RESOLVED": frozenset({"REOPENED"}),                                                # staff may reopen a closed case; citizens reopen through verification
    "REJECTED": frozenset(),                                                            # terminal
}
TERMINAL = frozenset({"REJECTED"})
CLOSED = frozenset({"RESOLVED", "REJECTED"})
OPEN_STATES = frozenset(STATES) - CLOSED - {"VERIFIED"}
PRE_PROCESSING = frozenset({"SUBMITTED", "AI_PROCESSING", "NEEDS_REVIEW"})            # the only states in which a citizen may still edit a case (§51A.4)
TRIAGEABLE = frozenset({"NEEDS_REVIEW", "ASSIGNED", "WORK_ORDER_CREATED", "REOPENED"})
# states whose entry the reporter is told about (the micro-steps SUBMITTED -> AI_PROCESSING -> NEEDS_REVIEW are not news)
NOTIFY_STATES = {"ASSIGNED": "CASE_ASSIGNED", "IN_PROGRESS": "CASE_UPDATED", "AWAITING_VERIFICATION": "VERIFICATION_REQUESTED", "RESOLVED": "CASE_RESOLVED",
                 "REOPENED": "CASE_UPDATED", "REJECTED": "CASE_UPDATED", "WORK_ORDER_CREATED": "CASE_UPDATED"}
AUDITED = {"REJECTED": "CASE_REJECTED", "RESOLVED": "CASE_RESOLVED", "REOPENED": "CASE_REOPENED", "VERIFIED": "CASE_VERIFIED"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def add_event(db: Session, case_id: str, event_type: str, *, actor_id: str | None, actor_role: str | None, metadata: dict[str, Any] | None = None,
              visibility: str = "PUBLIC") -> CaseEvent:
    ev = CaseEvent(case_id=case_id, event_type=event_type, actor_id=actor_id, actor_role=actor_role, visibility=visibility, event_metadata=metadata or {})
    db.add(ev)
    db.flush()
    return ev


def can_transition(frm: str, to: str) -> bool:
    return to in TRANSITIONS.get(frm, frozenset())


def transition(db: Session, case: CivicCase, to: str, *, actor_id: str | None, actor_role: str | None, metadata: dict[str, Any] | None = None,
               reason: str | None = None, notify_reporter: bool = True) -> CivicCase:
    frm = case.status
    if to not in TRANSITIONS.get(frm, frozenset()):
        raise CivicConnectException("INVALID_STATE_TRANSITION", f"A case cannot move from {frm} to {to}.", 409,
                                    {"from": frm, "to": to, "allowed": sorted(TRANSITIONS.get(frm, ()))})
    if to == "REJECTED" and not (reason and reason.strip()):
        raise CivicConnectException("REASON_REQUIRED", "Rejecting a case needs a reason.", 422, {"field": "reason"})
    now = utcnow()
    case.status = to
    case.updated_at = now
    if to in CLOSED:
        case.closed_at = now
    if to == "REOPENED":
        case.closed_at = None
        case.reopen_count = (case.reopen_count or 0) + 1
    meta = {"from": frm, "to": to, **(metadata or {})}
    if reason:
        meta["reason"] = reason
    add_event(db, case.id, "STATUS_CHANGED", actor_id=actor_id, actor_role=actor_role, metadata=meta)
    if to in AUDITED:
        record_audit(db, actor_id=actor_id, action=AUDITED[to], entity_type="CIVIC_CASE", entity_id=case.id, before={"status": frm}, after={"status": to, "reason": reason})
    if notify_reporter and to in NOTIFY_STATES and case.reporter_id and case.reporter_id != actor_id:
        notify(db, [case.reporter_id], NOTIFY_STATES[to], {"case_id": case.id, "case_number": case.case_number, "status": to,
                                                           "title": f"Case {case.case_number}: {to.replace('_', ' ').title()}", "message": reason or ""})
    return case
