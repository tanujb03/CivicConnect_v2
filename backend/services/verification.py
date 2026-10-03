"""Citizen verification (§51A.10) and the reopen / reject actions of §35."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.exceptions import CivicConnectException
from backend.core.permissions import STAFF_ROLES, forbidden
from backend.models import CivicCase, Support, User, Verification
from backend.schemas.case import VerificationIn
from backend.services import evidence as evidence_service
from backend.services.audit import record_audit
from backend.services.notifications import notify
from backend.services.workflow import add_event, transition

# Verification policy (design §51A.10 "according to policy"): configuration, not scattered if-statements.
#   YES             -> VERIFIED -> RESOLVED
#   STILL_OCCURRING -> REOPENED and escalated one priority tier
#   NO              -> REOPENED (the fix did not work)
#   PARTIAL         -> stays AWAITING_VERIFICATION and staff are told: a human decides
VERIFICATION_POLICY = {"YES": "RESOLVE", "STILL_OCCURRING": "REOPEN_ESCALATE", "NO": "REOPEN", "PARTIAL": "FLAG_STAFF"}
PRIORITY_LADDER = ["LOW", "NORMAL", "HIGH", "URGENT", "CRITICAL"]
ESCALATION_CAP = "URGENT"


def _may_verify(db: Session, user: User, case: CivicCase) -> bool:
    if user.role in STAFF_ROLES:
        return True
    if user.role != "citizen":
        return False
    if case.reporter_id == user.id:
        return True
    return db.execute(select(Support.id).where(Support.case_id == case.id, Support.user_id == user.id, Support.role == "CONTRIBUTOR")).first() is not None


def escalate(priority: str) -> str:
    i = PRIORITY_LADDER.index(priority) if priority in PRIORITY_LADDER else 1
    return PRIORITY_LADDER[min(i + 1, PRIORITY_LADDER.index(ESCALATION_CAP))] if i < PRIORITY_LADDER.index(ESCALATION_CAP) else priority


def record(db: Session, user: User, case: CivicCase, body: VerificationIn) -> tuple[Verification, bool]:
    if not _may_verify(db, user, case):
        raise forbidden("Only the reporter, a contributor or staff may verify the resolution.")
    if case.status != "AWAITING_VERIFICATION":
        raise CivicConnectException("NOT_AWAITING_VERIFICATION", "This case is not waiting for verification.", 409, {"status": case.status})
    v = Verification(case_id=case.id, citizen_id=user.id, result=body.result, comment=body.comment)
    db.add(v)
    db.flush()
    if body.evidence_ids:
        evs = evidence_service.attach(db, user, body.evidence_ids, case, purpose="VERIFICATION")
        v.evidence_id = evs[0].id
        for e in evs:
            e.verification_id = v.id
    add_event(db, case.id, "VERIFICATION_RECORDED", actor_id=user.id, actor_role=user.role, metadata={"result": body.result, "verification_id": v.id})
    record_audit(db, actor_id=user.id, action="VERIFICATION_RECORDED", entity_type="CIVIC_CASE", entity_id=case.id, before={"status": case.status}, after={"result": body.result})
    action, reopened = VERIFICATION_POLICY[body.result], False
    if action == "RESOLVE":
        transition(db, case, "VERIFIED", actor_id=user.id, actor_role=user.role, metadata={"verification_id": v.id}, notify_reporter=False)
        transition(db, case, "RESOLVED", actor_id=None, actor_role="SYSTEM", metadata={"verification_id": v.id})
    elif action in ("REOPEN", "REOPEN_ESCALATE"):
        meta = {"verification_id": v.id, "result": body.result}
        if action == "REOPEN_ESCALATE":
            new = escalate(case.priority)
            if new != case.priority:
                meta["escalated_from"], meta["escalated_to"] = case.priority, new
                case.priority = new
        transition(db, case, "REOPENED", actor_id=user.id, actor_role=user.role, metadata=meta, reason=body.comment or f"Citizen reported: {body.result}")
        reopened = True
        _notify_staff(db, case, f"Case {case.case_number} was reopened by verification ({body.result})")
    else:                                                    # FLAG_STAFF
        _notify_staff(db, case, f"Case {case.case_number}: partial fix reported by the citizen; needs a decision")
    db.flush()
    return v, reopened


def _notify_staff(db: Session, case: CivicCase, message: str) -> None:
    q = select(User.id).where(User.is_active.is_(True), User.role.in_(["operator", "department_manager"]), User.department_id == case.department_id) if case.department_id else None
    ids = list(db.execute(q).scalars()) if q is not None else []
    notify(db, ids, "CASE_UPDATED", {"case_id": case.id, "case_number": case.case_number, "title": message, "message": ""})


def reopen(db: Session, user: User, case: CivicCase, reason: str) -> CivicCase:
    if user.role not in STAFF_ROLES:
        raise forbidden()
    if case.status not in ("RESOLVED", "AWAITING_VERIFICATION"):
        raise CivicConnectException("INVALID_STATE", f"A case in state {case.status} cannot be reopened.", 409, {"status": case.status})
    return transition(db, case, "REOPENED", actor_id=user.id, actor_role=user.role, reason=reason)


def reject(db: Session, user: User, case: CivicCase, reason: str) -> CivicCase:
    if user.role not in STAFF_ROLES:
        raise forbidden()
    return transition(db, case, "REJECTED", actor_id=user.id, actor_role=user.role, reason=reason)


def review_after_verification(case_id: str, result: str, comment: str | None) -> dict | None:
    """AI-4 hook after a citizen verification committed (flag only; staff-only output)."""
    try:
        from backend.ai_gateway import get_gateway
        from backend.ai_gateway.contracts import ResolutionReviewIn
        from backend.ai_gateway.service import SYSTEM_ACTOR
        gw = get_gateway()
        if gw.repo.get_case(case_id) is None:
            return None
        out = gw.review_resolution(case_id, ResolutionReviewIn(citizen_verification=result, citizen_comment=comment), SYSTEM_ACTOR)
        return out.model_dump(mode="json")
    except Exception:
        return None
