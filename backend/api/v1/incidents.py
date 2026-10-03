from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from backend.api.deps import IdempotencyHeader, idempotent
from backend.core.permissions import require_capability
from backend.core.security import current_user
from backend.db.session import get_db
from backend.models import User
from backend.schemas.common import Page
from backend.schemas.incident import IncidentAddCase, IncidentCreate, IncidentDetail, IncidentOut, IncidentPatch
from backend.services import incidents as incident_service

router = APIRouter()


@router.post("", response_model=IncidentOut, status_code=201)
@router.post("/", response_model=IncidentOut, status_code=201, include_in_schema=False)
def create_incident(body: IncidentCreate, response: Response, idempotency_key: Optional[str] = IdempotencyHeader, user: User = Depends(require_capability("manage_incidents")),
                    db: Session = Depends(get_db)):
    """§51A.14: groups related cases under a geographic boundary. Ward officers and above."""
    def handler():
        inc = incident_service.create(db, user, body)
        return 201, incident_service.serialize(db, inc), inc.id
    return idempotent(db, response, user_id=user.id, key=idempotency_key, method="POST", path="/incidents", payload=body.model_dump(mode="json"), handler=handler)


@router.get("", response_model=Page[IncidentOut])
@router.get("/", response_model=Page[IncidentOut], include_in_schema=False)
def list_incidents(status: Optional[str] = None, cursor: Optional[str] = None, limit: Optional[int] = Query(default=None, ge=1), user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    rows, nxt = incident_service.list_incidents(db, user, status=status, cursor=cursor, limit=limit)
    return {"items": [incident_service.serialize(db, i) for i in rows], "next_cursor": nxt}


@router.get("/{incident_id}", response_model=IncidentDetail)
def get_incident(incident_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return incident_service.detail(db, user, incident_service.get_or_404(db, incident_id))


@router.post("/{incident_id}/cases")
def add_case_to_incident(incident_id: str, body: IncidentAddCase, response: Response, idempotency_key: Optional[str] = IdempotencyHeader,
                         user: User = Depends(require_capability("manage_incidents")), db: Session = Depends(get_db)):
    def handler():
        inc = incident_service.get_or_404(db, incident_id)
        added = incident_service.add_case(db, user, inc, body.case_id)
        return 200, {"incident_id": inc.id, "case_id": body.case_id, "added": added}, inc.id
    return idempotent(db, response, user_id=user.id, key=idempotency_key, method="POST", path=f"/incidents/{incident_id}/cases", payload=body.model_dump(), handler=handler)


@router.patch("/{incident_id}", response_model=IncidentOut)
def patch_incident(incident_id: str, body: IncidentPatch, response: Response, idempotency_key: Optional[str] = IdempotencyHeader,
                   user: User = Depends(require_capability("manage_incidents")), db: Session = Depends(get_db)):
    def handler():
        inc = incident_service.update(db, user, incident_service.get_or_404(db, incident_id), title=body.title, description=body.description, status=body.status)
        return 200, incident_service.serialize(db, inc), inc.id
    return idempotent(db, response, user_id=user.id, key=idempotency_key, method="PATCH", path=f"/incidents/{incident_id}", payload=body.model_dump(), handler=handler)
