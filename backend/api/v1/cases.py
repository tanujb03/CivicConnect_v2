from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.ai_gateway import AIGateway, get_actor, get_gateway
from backend.ai_gateway.contracts import (
    FusionAnalyzeResponse, IntakeAnalyzeRequest, IntakeAnalyzeResponse, TriageAnalyzeResponse, TriageDecisionRequest, TriageDecisionResponse,
)
from backend.ai_gateway.service import Actor
from backend.api.deps import IdempotencyHeader, idempotent
from backend.core.config import settings
from backend.core.exceptions import CivicConnectException
from backend.core.permissions import require_capability, require_staff
from backend.core.security import current_user
from backend.db.session import get_db
from backend.models import User
from backend.schemas.case import (
    CaseCreate, CaseCreated, CaseDetail, CaseOut, CasePatch, ContributorIn, RejectIn, ReopenIn, TimelineItem, VerificationIn, VerificationOut,
)
from backend.schemas.common import Page
from backend.schemas.evidence import EvidenceOut
from backend.schemas.work_order import WorkOrderCreate, WorkOrderOut
from backend.services import cases as case_service
from backend.services import evidence as evidence_service
from backend.services import timeline as timeline_service
from backend.services import verification as verification_service
from backend.services import work_orders as work_order_service

router = APIRouter()


def _authorize_ai_case(db: Session, actor: Actor, case_id: str) -> None:
    """With the SQL store the AI endpoints obey the same object-level rules as the case endpoints (an operator cannot analyse another department's case)."""
    if settings.AI_GATEWAY_STORE != "sql":
        return
    user = db.get(User, actor.user_id)
    if user is None or not user.is_active:
        raise CivicConnectException("AUTH_INVALID_TOKEN", "The account no longer exists or is inactive.", 401)
    case_service.get_visible_case(db, user, case_id)


# ---------------------------------------------------------------------------------------------------------------- AI (§51A.5 / 51A.7 / 51A.8)
# Plain ``def`` handlers on purpose: the adapter is synchronous (HTTP + numpy) and FastAPI runs these in its thread pool.
@router.post("/intake/analyze", response_model=IntakeAnalyzeResponse)
def analyze_intake(request: IntakeAnalyzeRequest, actor: Actor = Depends(get_actor), gateway: AIGateway = Depends(get_gateway), db: Session = Depends(get_db)):
    """``language_hint`` (the language the citizen chose for this report) goes to speech-to-text; without it the profile's ``preferred_language`` is used when it is Hindi or
    Marathi. English is never taken from the profile: it is the default value, and Whisper obeys the hint (a Hindi clip hinted ``en`` comes back transliterated into Latin script)."""
    if not request.language_hint and settings.AI_GATEWAY_STORE == "sql":                  # the demo store has no user table
        user = db.get(User, actor.user_id)
        if user is not None and user.preferred_language in ("hi", "mr"):
            request = request.model_copy(update={"language_hint": user.preferred_language})
    return gateway.intake(request, actor)


@router.post("/{case_id}/fusion/analyze", response_model=FusionAnalyzeResponse)
def analyze_fusion(case_id: str, actor: Actor = Depends(get_actor), gateway: AIGateway = Depends(get_gateway), db: Session = Depends(get_db)):
    _authorize_ai_case(db, actor, case_id)
    return gateway.fusion(case_id, actor)


@router.post("/{case_id}/triage/analyze", response_model=TriageAnalyzeResponse)
def analyze_triage(case_id: str, actor: Actor = Depends(get_actor), gateway: AIGateway = Depends(get_gateway), db: Session = Depends(get_db)):
    _authorize_ai_case(db, actor, case_id)
    return gateway.triage(case_id, actor)


@router.post("/{case_id}/triage/decision", response_model=TriageDecisionResponse)
def apply_triage_decision(case_id: str, decision: TriageDecisionRequest, response: Response, actor: Actor = Depends(get_actor), gateway: AIGateway = Depends(get_gateway),
                          db: Session = Depends(get_db), idempotency_key: Optional[str] = IdempotencyHeader):
    """Records the authorized human triage decision; a decision that differs from the stored AI recommendation is audited as an AI override."""
    _authorize_ai_case(db, actor, case_id)

    def handler():
        out = gateway.triage_decision(case_id, decision, actor)
        return 200, out.model_dump(mode="json"), case_id
    return idempotent(db, response, user_id=actor.user_id, key=idempotency_key, method="POST", path=f"/cases/{case_id}/triage/decision",
                      payload=decision.model_dump(mode="json"), handler=handler, required=False)


# ---------------------------------------------------------------------------------------------------------------- §51A.4 cases
@router.post("", response_model=CaseCreated, status_code=201)
@router.post("/", response_model=CaseCreated, status_code=201, include_in_schema=False)
def create_case(body: CaseCreate, response: Response, idempotency_key: Optional[str] = IdempotencyHeader, user: User = Depends(require_capability("create_case")),
                db: Session = Depends(get_db)):
    """The server owns status, priority, assignment and timestamps. A repeated ``client_case_id`` returns the existing case."""
    def handler():
        case, created = case_service.create_case(db, user, body)
        return (201 if created else 200), {"case": case_service.view_case(db, user, case)}, case.id
    return idempotent(db, response, user_id=user.id, key=idempotency_key, method="POST", path="/cases", payload=body.model_dump(mode="json"), handler=handler)


@router.get("", response_model=Page[CaseOut])
@router.get("/", response_model=Page[CaseOut], include_in_schema=False)
def list_cases(status: Optional[str] = None, category: Optional[str] = None, priority: Optional[str] = None, ward_id: Optional[str] = None,
               department_id: Optional[str] = None, q: Optional[str] = Query(default=None, description="case number / title / description"),
               from_: Optional[datetime] = Query(default=None, alias="from"), until: Optional[datetime] = None, sort: Optional[str] = None,
               cursor: Optional[str] = None, limit: Optional[int] = Query(default=None, ge=1), user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows, nxt = case_service.list_cases(db, user, status=status, category=category, priority=priority, ward_id=ward_id, department_id=department_id, q=q, from_=from_,
                                        until=until, sort=sort, cursor=cursor, limit=limit)
    return {"items": [case_service.serialize_case(c) for c in rows], "next_cursor": nxt}


@router.get("/{case_id}", response_model=CaseDetail)
def get_case(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = case_service.get_visible_case(db, user, case_id)
    return case_service.serialize_detail(db, user, case)


@router.patch("/{case_id}", response_model=CaseOut)
def patch_case(case_id: str, body: CasePatch, response: Response, idempotency_key: Optional[str] = IdempotencyHeader, user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    def handler():
        case = case_service.get_visible_case(db, user, case_id)
        case_service.patch_case(db, user, case, body)
        return 200, case_service.serialize_case(case), case.id
    return idempotent(db, response, user_id=user.id, key=idempotency_key, method="PATCH", path=f"/cases/{case_id}", payload=body.model_dump(mode="json"), handler=handler)


@router.post("/{case_id}/contributors")
def add_contributor(case_id: str, body: ContributorIn, response: Response, idempotency_key: Optional[str] = IdempotencyHeader, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    def handler():
        case = case_service.get_visible_case(db, user, case_id)
        s = case_service.add_contributor(db, user, case, body.user_id)
        return 201, {"case_id": case.id, "user_id": s.user_id, "role": s.role}, s.id
    return idempotent(db, response, user_id=user.id, key=idempotency_key, method="POST", path=f"/cases/{case_id}/contributors", payload=body.model_dump(), handler=handler)


@router.post("/{case_id}/support")
def support_case(case_id: str, response: Response, idempotency_key: Optional[str] = IdempotencyHeader, user: User = Depends(require_capability("create_case")),
                 db: Session = Depends(get_db)):
    """A citizen backs a case (raises its support count and, through the §36 rules, may raise its priority). Idempotent per user."""
    def handler():
        case = db.get(case_service.CivicCase, case_id)
        if case is None:
            raise CivicConnectException("CASE_NOT_FOUND", "The requested civic case does not exist.", 404)
        _, created = case_service.add_support(db, user, case)
        return 200, {"case_id": case.id, "support_count": case.support_count, "supported": True, "created": created}, case.id
    return idempotent(db, response, user_id=user.id, key=idempotency_key, method="POST", path=f"/cases/{case_id}/support", payload={}, handler=handler)


@router.delete("/{case_id}/support")
def unsupport_case(case_id: str, response: Response, idempotency_key: Optional[str] = IdempotencyHeader, user: User = Depends(current_user), db: Session = Depends(get_db)):
    def handler():
        case = db.get(case_service.CivicCase, case_id)
        if case is None:
            raise CivicConnectException("CASE_NOT_FOUND", "The requested civic case does not exist.", 404)
        removed = case_service.remove_support(db, user, case)
        return 200, {"case_id": case.id, "support_count": case.support_count, "supported": False, "removed": removed}, case.id
    return idempotent(db, response, user_id=user.id, key=idempotency_key, method="DELETE", path=f"/cases/{case_id}/support", payload={}, handler=handler)


# ---------------------------------------------------------------------------------------------------------------- evidence attach (§41)
class AttachEvidenceIn(BaseModel):
    evidence_ids: list[str] = Field(min_length=1, max_length=20)


@router.post("/{case_id}/evidence", response_model=list[EvidenceOut])
def attach_evidence(case_id: str, body: AttachEvidenceIn, response: Response, idempotency_key: Optional[str] = IdempotencyHeader, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    """Attach more READY evidence you uploaded to a case you may see."""
    def handler():
        case = case_service.get_visible_case(db, user, case_id)
        evs = evidence_service.attach(db, user, body.evidence_ids, case)
        return 200, [evidence_service.serialize(e) for e in evs], case.id
    return idempotent(db, response, user_id=user.id, key=idempotency_key, method="POST", path=f"/cases/{case_id}/evidence", payload=body.model_dump(), handler=handler)


# ---------------------------------------------------------------------------------------------------------------- §51A.9 work order (case scoped)
@router.post("/{case_id}/work-orders", response_model=WorkOrderOut, status_code=201)
def create_case_work_order(case_id: str, body: WorkOrderCreate, response: Response, idempotency_key: Optional[str] = IdempotencyHeader,
                           user: User = Depends(require_capability("create_work_order")), db: Session = Depends(get_db)):
    def handler():
        case = case_service.get_visible_case(db, user, case_id)
        wo = work_order_service.create(db, user, case, body)
        return 201, work_order_service.serialize(wo, case.case_number), wo.id
    return idempotent(db, response, user_id=user.id, key=idempotency_key, method="POST", path=f"/cases/{case_id}/work-orders", payload=body.model_dump(mode="json"), handler=handler)


# ---------------------------------------------------------------------------------------------------------------- §51A.10 verification, §51A.11 timeline
@router.post("/{case_id}/verification", response_model=VerificationOut, status_code=201)
def verify_case(case_id: str, body: VerificationIn, response: Response, idempotency_key: Optional[str] = IdempotencyHeader,
                user: User = Depends(require_capability("verify_resolution")), db: Session = Depends(get_db)):
    """Records the citizen's verdict. ``YES`` resolves the case; ``NO`` / ``STILL_OCCURRING`` reopen it (STILL_OCCURRING also escalates); ``PARTIAL`` asks staff to decide."""
    def handler():
        case = case_service.get_visible_case(db, user, case_id)
        v, reopened = verification_service.record(db, user, case, body)
        return 201, {"id": v.id, "case_id": case.id, "result": v.result, "case_status": case.status, "reopened": reopened, "created_at": v.created_at}, v.id
    out = idempotent(db, response, user_id=user.id, key=idempotency_key, method="POST", path=f"/cases/{case_id}/verification", payload=body.model_dump(), handler=handler)
    if response.headers.get("Idempotent-Replayed") != "true":
        verification_service.review_after_verification(case_id, body.result, body.comment)       # AI-4 flags; advisory, staff-only, after commit
    return out


@router.get("/{case_id}/timeline", response_model=Page[TimelineItem])
def get_timeline(case_id: str, cursor: Optional[str] = None, limit: Optional[int] = Query(default=None, ge=1), user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = case_service.get_visible_case(db, user, case_id)
    rows, nxt = timeline_service.events_for(db, user, case.id, cursor=cursor, limit=limit)
    staff = user.role in case_service.STAFF_ROLES
    return {"items": [timeline_service.serialize(e, staff=staff) for e in rows], "next_cursor": nxt}


# ---------------------------------------------------------------------------------------------------------------- §35 reject / reopen (additive)
@router.post("/{case_id}/reject", response_model=CaseOut)
def reject_case(case_id: str, body: RejectIn, response: Response, idempotency_key: Optional[str] = IdempotencyHeader, user: User = Depends(require_staff),
                db: Session = Depends(get_db)):
    """A rejected case needs an authorized actor, a reason and an audit event (§35)."""
    def handler():
        case = case_service.get_visible_case(db, user, case_id)
        verification_service.reject(db, user, case, body.reason)
        return 200, case_service.view_case(db, user, case), case.id
    return idempotent(db, response, user_id=user.id, key=idempotency_key, method="POST", path=f"/cases/{case_id}/reject", payload=body.model_dump(), handler=handler)


@router.post("/{case_id}/reopen", response_model=CaseOut)
def reopen_case(case_id: str, body: ReopenIn, response: Response, idempotency_key: Optional[str] = IdempotencyHeader, user: User = Depends(require_staff),
                db: Session = Depends(get_db)):
    def handler():
        case = case_service.get_visible_case(db, user, case_id)
        verification_service.reopen(db, user, case, body.reason)
        return 200, case_service.view_case(db, user, case), case.id
    return idempotent(db, response, user_id=user.id, key=idempotency_key, method="POST", path=f"/cases/{case_id}/reopen", payload=body.model_dump(), handler=handler)
