from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.deps import IdempotencyHeader, idempotent
from backend.core.permissions import STAFF_ROLES, require_capability, require_staff
from backend.core.security import current_user
from backend.db.session import get_db
from backend.models import CivicCase, User
from backend.schemas.common import Page
from backend.schemas.work_order import WorkOrderComplete, WorkOrderCreateLegacy, WorkOrderDetail, WorkOrderOut, WorkOrderPatch
from backend.services import cases as case_service
from backend.services import work_orders as wo_service

router = APIRouter()


class CompleteOut(WorkOrderOut):
    resolution_review: Optional[dict] = None          # AI-4 flags, staff only


class CancelIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


def _out(db: Session, w) -> dict:
    case = db.get(CivicCase, w.case_id)
    return wo_service.serialize(w, case.case_number if case else None)


@router.post("", response_model=WorkOrderOut, status_code=201)
@router.post("/", response_model=WorkOrderOut, status_code=201, include_in_schema=False)
def create_work_order(body: WorkOrderCreateLegacy, response: Response, idempotency_key: Optional[str] = IdempotencyHeader,
                      user: User = Depends(require_capability("create_work_order")), db: Session = Depends(get_db)):
    """Same as ``POST /cases/{case_id}/work-orders`` (§51A.9) with the case id in the body (design §41 form)."""
    def handler():
        case = case_service.get_visible_case(db, user, body.case_id)
        wo = wo_service.create(db, user, case, body)
        return 201, wo_service.serialize(wo, case.case_number), wo.id
    return idempotent(db, response, user_id=user.id, key=idempotency_key, method="POST", path="/work-orders", payload=body.model_dump(mode="json"), handler=handler)


@router.get("", response_model=Page[WorkOrderOut])
@router.get("/", response_model=Page[WorkOrderOut], include_in_schema=False)
def list_work_orders(status: Optional[str] = None, case_id: Optional[str] = None, cursor: Optional[str] = None, limit: Optional[int] = Query(default=None, ge=1),
                     user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Role-scoped: a field worker sees their own, staff see those of cases they may see."""
    rows, nxt = wo_service.list_for(db, user, status=status, case_id=case_id, cursor=cursor, limit=limit)
    return {"items": [_out(db, w) for w in rows], "next_cursor": nxt}


@router.get("/{work_order_id}", response_model=WorkOrderDetail)
def get_work_order(work_order_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return wo_service.detail(db, user, wo_service.get_visible(db, user, work_order_id))


@router.patch("/{work_order_id}", response_model=WorkOrderOut)
def patch_work_order(work_order_id: str, body: WorkOrderPatch, response: Response, idempotency_key: Optional[str] = IdempotencyHeader, user: User = Depends(require_staff),
                     db: Session = Depends(get_db)):
    def handler():
        wo = wo_service.get_visible(db, user, work_order_id)
        wo_service.update(db, user, wo, assignee_id=body.assignee_id, instructions=body.instructions, due_at=body.due_at, priority=body.priority)
        return 200, _out(db, wo), wo.id
    return idempotent(db, response, user_id=user.id, key=idempotency_key, method="PATCH", path=f"/work-orders/{work_order_id}", payload=body.model_dump(mode="json"), handler=handler)


@router.post("/{work_order_id}/start", response_model=WorkOrderOut)
def start_work_order(work_order_id: str, response: Response, idempotency_key: Optional[str] = IdempotencyHeader, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Records the work start time and the worker identity (§51A.9)."""
    def handler():
        wo = wo_service.start(db, user, wo_service.get_visible(db, user, work_order_id))
        return 200, _out(db, wo), wo.id
    return idempotent(db, response, user_id=user.id, key=idempotency_key, method="POST", path=f"/work-orders/{work_order_id}/start", payload={}, handler=handler)


@router.post("/{work_order_id}/complete", response_model=CompleteOut)
def complete_work_order(work_order_id: str, body: WorkOrderComplete, response: Response, idempotency_key: Optional[str] = IdempotencyHeader,
                        user: User = Depends(require_capability("submit_resolution")), db: Session = Depends(get_db)):
    """Completing work does NOT close the case: it moves it to AWAITING_VERIFICATION and asks the reporter to verify (§51A.9)."""
    def handler():
        wo = wo_service.complete(db, user, wo_service.get_visible(db, user, work_order_id), body)
        return 200, _out(db, wo), wo.id
    out = idempotent(db, response, user_id=user.id, key=idempotency_key, method="POST", path=f"/work-orders/{work_order_id}/complete", payload=body.model_dump(), handler=handler)
    if response.headers.get("Idempotent-Replayed") != "true":
        review = wo_service.review_after_completion(out["case_id"], work_order_id, body.notes, body.resolution_evidence_ids)       # AI-4 flags after commit
        if user.role in STAFF_ROLES:
            out = {**out, "resolution_review": review}
    return out


@router.post("/{work_order_id}/cancel", response_model=WorkOrderOut)
def cancel_work_order(work_order_id: str, body: CancelIn, response: Response, idempotency_key: Optional[str] = IdempotencyHeader, user: User = Depends(require_staff),
                      db: Session = Depends(get_db)):
    def handler():
        wo = wo_service.cancel(db, user, wo_service.get_visible(db, user, work_order_id), body.reason)
        return 200, _out(db, wo), wo.id
    return idempotent(db, response, user_id=user.id, key=idempotency_key, method="POST", path=f"/work-orders/{work_order_id}/cancel", payload=body.model_dump(), handler=handler)
