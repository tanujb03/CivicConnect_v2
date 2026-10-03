"""Incident mode (§51A.14, design §38): a geographic grouping of related cases with its own timeline."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.exceptions import CivicConnectException
from backend.core.pagination import clamp_limit, paginate
from backend.core.permissions import STAFF_ROLES, forbidden
from backend.models import CivicCase, Incident, IncidentCase, User, WorkOrder
from backend.schemas.incident import IncidentCreate
from backend.services import cases as case_service
from backend.services import taxonomy as tx
from backend.services.audit import record_audit
from backend.services.geo import geometry_center, valid_geometry
from backend.services.notifications import notify
from backend.services.workflow import add_event, utcnow


def _require_manage(user: User) -> None:
    if user.role not in ("ward_officer", "city_admin", "system_admin"):
        raise forbidden("Only ward officers and city administrators manage incidents.", capability="manage_incidents")


def _view_check(user: User) -> None:
    if user.role not in STAFF_ROLES | {"overlooker"}:
        raise forbidden("Your role may not view incidents.", capability="view_incidents")


def get_or_404(db: Session, incident_id: str) -> Incident:
    inc = db.get(Incident, incident_id)
    if inc is None:
        raise CivicConnectException("INCIDENT_NOT_FOUND", "The incident does not exist.", 404)
    return inc


def _link(db: Session, user: User, inc: Incident, case: CivicCase) -> bool:
    if db.get(IncidentCase, (inc.id, case.id)) is not None:
        return False
    db.add(IncidentCase(incident_id=inc.id, case_id=case.id, added_by=user.id))
    db.flush()
    case_service.apply_assessment(db, case)                  # §36 "incident context" is one of the priority inputs
    add_event(db, case.id, "INCIDENT_LINKED", actor_id=user.id, actor_role=user.role, metadata={"incident_id": inc.id, "title": inc.title})
    return True


def create(db: Session, user: User, body: IncidentCreate) -> Incident:
    _require_manage(user)
    if not valid_geometry(body.boundary):
        raise CivicConnectException("VALIDATION_ERROR", "boundary must be a GeoJSON Polygon, MultiPolygon or Point.", 422, {"field": "boundary"})
    if body.category and tx.taxonomy().resolve_category(body.category) is None:
        raise CivicConnectException("VALIDATION_ERROR", "Unknown category.", 422, {"field": "category"})
    centre = geometry_center(body.boundary)
    inc = Incident(title=body.title.strip(), description=body.description, category=body.category, geometry=body.boundary, center_lat=centre[0] if centre else None,
                   center_lon=centre[1] if centre else None, ward_id=case_service.find_ward(db, *centre) if centre else None, status="ACTIVE", created_by=user.id)
    db.add(inc)
    db.flush()
    cases = [case_service.get_visible_case(db, user, cid) for cid in dict.fromkeys(body.case_ids)]
    for c in cases:
        _link(db, user, inc, c)
    record_audit(db, actor_id=user.id, action="INCIDENT_CREATED", entity_type="INCIDENT", entity_id=inc.id, before=None, after={"title": inc.title, "cases": len(cases)})
    audience = list(db.execute(select(User.id).where(User.is_active.is_(True), User.role == "city_admin")).scalars())
    if inc.ward_id:
        audience += list(db.execute(select(User.id).where(User.is_active.is_(True), User.role == "ward_officer", User.ward_id == inc.ward_id)).scalars())
    audience += [c.reporter_id for c in cases]
    notify(db, [a for a in audience if a != user.id], "INCIDENT_CREATED", {"incident_id": inc.id, "title": f"Incident: {inc.title}", "message": "Related reports were grouped into an incident."})
    return inc


def add_case(db: Session, user: User, inc: Incident, case_id: str) -> bool:
    _require_manage(user)
    if inc.status != "ACTIVE":
        raise CivicConnectException("INVALID_STATE", "The incident has ended.", 409)
    return _link(db, user, inc, case_service.get_visible_case(db, user, case_id))


def update(db: Session, user: User, inc: Incident, *, title: str | None, description: str | None, status: str | None) -> Incident:
    _require_manage(user)
    before = {"title": inc.title, "description": inc.description, "status": inc.status}
    if title:
        inc.title = title.strip()
    if description is not None:
        inc.description = description
    if status and status != inc.status:
        inc.status = status
        inc.ended_at = utcnow() if status == "ENDED" else None
        for c in db.execute(select(CivicCase).join(IncidentCase, IncidentCase.case_id == CivicCase.id).where(IncidentCase.incident_id == inc.id)).scalars():
            case_service.apply_assessment(db, c)           # the incident bonus ends with the incident
    record_audit(db, actor_id=user.id, action="INCIDENT_UPDATED", entity_type="INCIDENT", entity_id=inc.id, before=before,
                 after={"title": inc.title, "description": inc.description, "status": inc.status})
    db.flush()
    return inc


def case_count(db: Session, incident_id: str) -> int:
    return db.execute(select(func.count()).select_from(IncidentCase).where(IncidentCase.incident_id == incident_id)).scalar_one()


def serialize(db: Session, inc: Incident) -> dict:
    return {"id": inc.id, "title": inc.title, "description": inc.description, "category": inc.category, "status": inc.status, "boundary": inc.geometry, "ward_id": inc.ward_id,
            "started_at": inc.started_at, "ended_at": inc.ended_at, "case_count": case_count(db, inc.id)}


def detail(db: Session, user: User, inc: Incident) -> dict:
    _view_check(user)
    out = serialize(db, inc)
    links = list(db.execute(select(IncidentCase).where(IncidentCase.incident_id == inc.id).order_by(IncidentCase.added_at)).scalars())
    staff = user.role in STAFF_ROLES
    visible_ids: list[str] = []
    if staff:
        clause = case_service.visibility_clause(user)
        q = select(CivicCase.id).where(CivicCase.id.in_([lk.case_id for lk in links]) if links else CivicCase.id == None)  # noqa: E711
        if clause is not True:
            q = q.where(clause)
        visible_ids = list(db.execute(q).scalars())
    out["case_ids"] = visible_ids
    cases = list(db.execute(select(CivicCase).where(CivicCase.id.in_(visible_ids))).scalars()) if visible_ids else []
    out["departments"] = sorted({c.department_id for c in cases if c.department_id})
    out["work_orders"] = [{"id": w.id, "case_id": w.case_id, "status": w.status, "department_id": w.department_id} for w in
                          (db.execute(select(WorkOrder).where(WorkOrder.case_id.in_(visible_ids))).scalars() if visible_ids else [])]
    out["timeline"] = [{"event_type": "INCIDENT_CREATED", "timestamp": inc.started_at, "metadata": {"title": inc.title}}] + \
                      [{"event_type": "CASE_LINKED", "timestamp": lk.added_at, "metadata": {"case_id": lk.case_id} if staff else {}} for lk in links] + \
                      ([{"event_type": "INCIDENT_ENDED", "timestamp": inc.ended_at, "metadata": {}}] if inc.ended_at else [])
    return out


def list_incidents(db: Session, user: User, *, status: str | None, cursor: str | None, limit: int | None) -> tuple[list[Incident], str | None]:
    _view_check(user)
    q = db.query(Incident)
    if status:
        q = q.filter(Incident.status == status.upper())
    return paginate(q, [(Incident.started_at, True), (Incident.id, True)], cursor, clamp_limit(limit), lambda i: [i.started_at, i.id])
