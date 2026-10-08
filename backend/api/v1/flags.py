"""Community flags (WP4). Mounted without a prefix: the routes carry their full paths."""
from typing import Optional

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.deps import IdempotencyHeader, idempotent
from backend.core.permissions import require_staff
from backend.core.security import current_user
from backend.db.session import get_db
from backend.models import User
from backend.schemas.platform import CaseFlagIn, CaseFlagOut, CaseFlagResolveIn
from backend.services import flags as flag_service

router = APIRouter()


class FlagCounts(BaseModel):
    by_kind: dict[str, int]
    by_status: dict[str, int]


class CaseFlagList(BaseModel):
    items: list[CaseFlagOut]
    counts: FlagCounts


@router.post("/cases/{case_id}/flags", response_model=CaseFlagOut, status_code=201)
def create_flag(case_id: str, body: CaseFlagIn, response: Response, idempotency_key: Optional[str] = IdempotencyHeader, user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    """Flag a case you may see. One flag per user, kind and case (409 FLAG_ALREADY_EXISTS); a reporter cannot flag their own case INAPPROPRIATE (403 FLAG_NOT_ALLOWED)."""
    def handler():
        f = flag_service.create(db, user, case_id, body)
        return 201, flag_service.serialize(f), f.id
    return idempotent(db, response, user_id=user.id, key=idempotency_key, method="POST", path=f"/cases/{case_id}/flags", payload=body.model_dump(mode="json"), handler=handler)


@router.get("/cases/{case_id}/flags", response_model=CaseFlagList)
def list_flags(case_id: str, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    """Staff with access to the case: every flag plus the counts by kind and by status (zeros included). Flaggers are never identified."""
    return flag_service.list_for_case(db, user, case_id)


@router.post("/flags/{flag_id}/resolve", response_model=CaseFlagOut)
def resolve_flag(flag_id: str, body: CaseFlagResolveIn, response: Response, idempotency_key: Optional[str] = IdempotencyHeader, user: User = Depends(require_staff),
                 db: Session = Depends(get_db)):
    """Staff mark an open flag UPHELD or DISMISSED (409 FLAG_ALREADY_RESOLVED when it is no longer open). Audited, with a timeline event."""
    def handler():
        f = flag_service.resolve(db, user, flag_id, body)
        return 200, flag_service.serialize(f), f.id
    return idempotent(db, response, user_id=user.id, key=idempotency_key, method="POST", path=f"/flags/{flag_id}/resolve", payload=body.model_dump(mode="json"), handler=handler)
