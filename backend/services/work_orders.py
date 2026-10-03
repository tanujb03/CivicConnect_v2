"""Work orders (§51A.9): create (dispatcher), start and complete (field worker); completion hands the case to the verification workflow."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.exceptions import CivicConnectException
from backend.core.pagination import clamp_limit, paginate
from backend.core.permissions import STAFF_ROLES, forbidden
from backend.models import AIAnalysis, CivicCase, User, WorkOrder
from backend.schemas.work_order import WorkOrderComplete, WorkOrderCreate
from backend.services import cases as case_service
from backend.services import evidence as evidence_service
from backend.services.audit import record_audit
from backend.services.notifications import notify
from backend.services.workflow import add_event, transition, utcnow

log = logging.getLogger("civicconnect.work_orders")
ACTIVE = frozenset({"ASSIGNED", "IN_PROGRESS"})


def serialize(w: WorkOrder, case_number: str | None = None) -> dict:
    return {"id": w.id, "case_id": w.case_id, "case_number": case_number, "department_id": w.department_id, "assignee_id": w.assigned_worker_id, "priority": w.priority,
            "due_at": w.deadline, "instructions": w.instructions, "notes": w.notes, "status": w.status, "started_at": w.started_at, "completed_at": w.completed_at,
            "created_at": w.created_at}


def _worker(db: Session, user_id: str, case: CivicCase) -> User:
    w = db.get(User, user_id)
    if w is None or not w.is_active or w.role != "field_worker":
        raise CivicConnectException("ASSIGNEE_INVALID", "The assignee must be an active field worker.", 422, {"assignee_id": user_id})
    if case.department_id and w.department_id and w.department_id != case.department_id:
        raise CivicConnectException("ASSIGNEE_WRONG_DEPARTMENT", "That field worker belongs to another department.", 422, {"assignee_id": user_id, "department_id": case.department_id})
    return w


def create(db: Session, user: User, case: CivicCase, body: WorkOrderCreate) -> WorkOrder:
    if user.role not in STAFF_ROLES:
        raise forbidden()
    if case.status not in ("ASSIGNED", "REOPENED"):
        raise CivicConnectException("INVALID_STATE", "A work order needs a triaged case (state ASSIGNED, or REOPENED after a failed fix).", 409, {"status": case.status})
    if db.execute(select(WorkOrder.id).where(WorkOrder.case_id == case.id, WorkOrder.status.in_(ACTIVE))).first():
        raise CivicConnectException("WORK_ORDER_EXISTS", "This case already has an active work order.", 409)
    worker = _worker(db, body.assignee_id, case)
    wo = WorkOrder(case_id=case.id, department_id=case.department_id, assigned_worker_id=worker.id, created_by=user.id, priority=case.priority,
                   deadline=body.due_at or case.sla_deadline, instructions=body.instructions, status="ASSIGNED")
    db.add(wo)
    db.flush()
    transition(db, case, "WORK_ORDER_CREATED", actor_id=user.id, actor_role=user.role, metadata={"work_order_id": wo.id})
    add_event(db, case.id, "WORK_ORDER_ASSIGNED", actor_id=user.id, actor_role=user.role, visibility="INTERNAL", metadata={"work_order_id": wo.id, "assignee_id": worker.id})
    record_audit(db, actor_id=user.id, action="CASE_ASSIGNED_TO_WORKER", entity_type="WORK_ORDER", entity_id=wo.id, before=None, after={"case_id": case.id, "assignee_id": worker.id})
    notify(db, [worker.id], "WORK_ORDER_ASSIGNED", {"case_id": case.id, "case_number": case.case_number, "work_order_id": wo.id, "title": f"New work order for case {case.case_number}",
                                                   "message": (body.instructions or "")[:200]})
    return wo


def visible_query(db: Session, user: User):
    q = db.query(WorkOrder)
    if user.role == "field_worker":
        return q.filter(WorkOrder.assigned_worker_id == user.id)
    if user.role in STAFF_ROLES:
        clause = case_service.visibility_clause(user)
        return q if clause is True else q.join(CivicCase, CivicCase.id == WorkOrder.case_id).filter(clause)
    raise forbidden("Your role has no work orders.", capability="view_work_orders")


def list_for(db: Session, user: User, *, status: str | None, case_id: str | None, cursor: str | None, limit: int | None) -> tuple[list[WorkOrder], str | None]:
    q = visible_query(db, user)
    if status:
        q = q.filter(WorkOrder.status.in_([s.strip().upper() for s in status.split(",") if s.strip()]))
    if case_id:
        q = q.filter(WorkOrder.case_id == case_id)
    return paginate(q, [(WorkOrder.created_at, True), (WorkOrder.id, True)], cursor, clamp_limit(limit), lambda w: [w.created_at, w.id])


def get_visible(db: Session, user: User, work_order_id: str) -> WorkOrder:
    wo = visible_query(db, user).filter(WorkOrder.id == work_order_id).first()
    if wo is None:
        raise CivicConnectException("WORK_ORDER_NOT_FOUND", "The work order does not exist.", 404)
    return wo


def detail(db: Session, user: User, wo: WorkOrder) -> dict:
    case = db.get(CivicCase, wo.case_id)
    out = serialize(wo, case.case_number if case else None)
    out["case"] = {"id": case.id, "case_number": case.case_number, "title": case.title, "description": case.description, "category": case.category, "subcategory": case.subcategory,
                   "priority": case.priority, "severity": case.severity, "status": case.status, "location": case_service.location_of(case), "sla_deadline": case.sla_deadline}
    evs = evidence_service.list_for_case(db, case.id)
    out["evidence"] = [evidence_service.serialize(e, with_url=True, with_location=True) for e in evs]
    out["resolution_review"] = None
    if user.role in STAFF_ROLES:
        row = db.execute(select(AIAnalysis).where(AIAnalysis.case_id == case.id, AIAnalysis.task_type == "resolution").order_by(AIAnalysis.created_at.desc())).scalars().first()
        if row:
            r = row.result_json or {}
            out["resolution_review"] = {"analysis_id": row.id, "consistency": r.get("consistency"), "unresolved_condition_suspected": r.get("unresolved_condition_suspected"),
                                        "recommend_verification_request": r.get("recommend_verification_request"), "reasons": r.get("reasons", []), "warnings": r.get("warnings", [])}
    return out


def _check_actor(user: User, wo: WorkOrder) -> None:
    if user.role == "field_worker" and wo.assigned_worker_id != user.id:
        raise CivicConnectException("WORK_ORDER_NOT_FOUND", "The work order does not exist.", 404)
    if user.role not in STAFF_ROLES and user.role != "field_worker":
        raise forbidden()


def start(db: Session, user: User, wo: WorkOrder) -> WorkOrder:
    _check_actor(user, wo)
    if wo.status != "ASSIGNED":
        raise CivicConnectException("INVALID_STATE", f"A work order in state {wo.status} cannot be started.", 409, {"status": wo.status})
    case = db.get(CivicCase, wo.case_id)
    wo.status, wo.started_at = "IN_PROGRESS", utcnow()
    transition(db, case, "IN_PROGRESS", actor_id=user.id, actor_role=user.role, metadata={"work_order_id": wo.id})
    add_event(db, case.id, "WORK_STARTED", actor_id=user.id, actor_role=user.role, visibility="INTERNAL", metadata={"work_order_id": wo.id})
    db.flush()
    return wo


def complete(db: Session, user: User, wo: WorkOrder, body: WorkOrderComplete) -> WorkOrder:
    _check_actor(user, wo)
    if wo.status != "IN_PROGRESS":
        raise CivicConnectException("INVALID_STATE", "Start the work order before completing it." if wo.status == "ASSIGNED" else f"A work order in state {wo.status} cannot be completed.",
                                    409, {"status": wo.status})
    if user.role == "field_worker" and not body.resolution_evidence_ids:
        raise CivicConnectException("RESOLUTION_EVIDENCE_REQUIRED", "Attach at least one photo of the finished work.", 422, {"field": "resolution_evidence_ids"})
    case = db.get(CivicCase, wo.case_id)
    evidence_service.attach(db, user, body.resolution_evidence_ids, case, purpose="RESOLUTION", work_order_id=wo.id)
    wo.status, wo.completed_at, wo.notes = "COMPLETED", utcnow(), body.notes
    transition(db, case, "RESOLUTION_SUBMITTED", actor_id=user.id, actor_role=user.role, metadata={"work_order_id": wo.id}, notify_reporter=False)
    add_event(db, case.id, "RESOLUTION_SUBMITTED", actor_id=user.id, actor_role=user.role, metadata={"work_order_id": wo.id, "evidence_count": len(body.resolution_evidence_ids)})
    # completing work does NOT close the case: it asks the citizen to verify (§51A.9)
    transition(db, case, "AWAITING_VERIFICATION", actor_id=None, actor_role="SYSTEM", metadata={"work_order_id": wo.id})
    db.flush()
    return wo


def review_after_completion(case_id: str, work_order_id: str, notes: str | None, evidence_ids: list[str]) -> dict | None:
    """AI-4 flag-only hook, run AFTER the completion committed (the gateway reads committed rows). Failure of any kind is logged and ignored; the result is shown to staff only."""
    try:
        from backend.ai_gateway import get_gateway
        from backend.ai_gateway.contracts import ResolutionReviewIn
        from backend.ai_gateway.service import SYSTEM_ACTOR
        gw = get_gateway()
        if gw.repo.get_case(case_id) is None:
            return None                                          # the gateway is not looking at this database (demo store)
        out = gw.review_resolution(case_id, ResolutionReviewIn(notes=notes or None, resolution_evidence_ids=list(evidence_ids)), SYSTEM_ACTOR)
        if out.unresolved_condition_suspected or out.consistency == "INCONSISTENT":
            from backend.db.session import session_scope
            with session_scope() as s:
                add_event(s, case_id, "RESOLUTION_FLAGGED", actor_id=None, actor_role="AI", visibility="INTERNAL",
                          metadata={"analysis_id": out.analysis_id, "consistency": out.consistency, "unresolved_condition_suspected": out.unresolved_condition_suspected,
                                    "work_order_id": work_order_id})
        return out.model_dump(mode="json")
    except Exception as e:
        log.warning("resolution review skipped: %s: %s", type(e).__name__, e)
        return None


def update(db: Session, user: User, wo: WorkOrder, *, assignee_id: str | None, instructions: str | None, due_at: datetime | None, priority: str | None) -> WorkOrder:
    if user.role not in STAFF_ROLES:
        raise forbidden()
    if wo.status not in ACTIVE:
        raise CivicConnectException("INVALID_STATE", f"A work order in state {wo.status} cannot be changed.", 409, {"status": wo.status})
    case = db.get(CivicCase, wo.case_id)
    before: dict[str, Any] = {}
    if assignee_id and assignee_id != wo.assigned_worker_id:
        if wo.status != "ASSIGNED":
            raise CivicConnectException("INVALID_STATE", "Work has started; reassigning now is not allowed.", 409)
        before["assignee_id"] = wo.assigned_worker_id
        wo.assigned_worker_id = _worker(db, assignee_id, case).id
        notify(db, [wo.assigned_worker_id], "WORK_ORDER_ASSIGNED", {"case_id": case.id, "case_number": case.case_number, "work_order_id": wo.id,
                                                                    "title": f"New work order for case {case.case_number}", "message": ""})
    if instructions is not None and instructions != wo.instructions:
        before["instructions"], wo.instructions = wo.instructions, instructions
    if due_at is not None and due_at != wo.deadline:
        before["due_at"], wo.deadline = (wo.deadline.isoformat() if wo.deadline else None), due_at
    if priority is not None and priority != wo.priority:
        before["priority"], wo.priority = wo.priority, priority
    if before:
        add_event(db, case.id, "WORK_ORDER_UPDATED", actor_id=user.id, actor_role=user.role, visibility="INTERNAL", metadata={"work_order_id": wo.id, "changed": sorted(before)})
        record_audit(db, actor_id=user.id, action="WORK_ORDER_UPDATED" if "assignee_id" not in before else "CASE_REASSIGNED", entity_type="WORK_ORDER", entity_id=wo.id,
                     before=before, after={"assignee_id": wo.assigned_worker_id, "due_at": wo.deadline.isoformat() if wo.deadline else None, "priority": wo.priority})
    db.flush()
    return wo


def cancel(db: Session, user: User, wo: WorkOrder, reason: str) -> WorkOrder:
    if user.role not in STAFF_ROLES:
        raise forbidden()
    if wo.status not in ACTIVE:
        raise CivicConnectException("INVALID_STATE", f"A work order in state {wo.status} cannot be cancelled.", 409, {"status": wo.status})
    case = db.get(CivicCase, wo.case_id)
    wo.status = "CANCELLED"
    wo.notes = reason
    transition(db, case, "ASSIGNED", actor_id=user.id, actor_role=user.role, metadata={"work_order_id": wo.id, "work_order_cancelled": True}, reason=reason)
    record_audit(db, actor_id=user.id, action="WORK_ORDER_CANCELLED", entity_type="WORK_ORDER", entity_id=wo.id, before={"status": "ACTIVE"}, after={"reason": reason})
    db.flush()
    return wo
