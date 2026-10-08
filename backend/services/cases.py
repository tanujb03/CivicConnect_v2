"""Civic case creation, visibility (object-level authorization, design §43), listing, edits, support and serialization."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.exceptions import CivicConnectException
from backend.core.pagination import clamp_limit, paginate
from backend.core.permissions import CITY_WIDE_ROLES, DEPARTMENT_ROLES, STAFF_ROLES, forbidden
from backend.models import CaseCounter, CivicCase, Support, User, Ward, WorkOrder
from backend.models.types import new_id
from backend.schemas.case import CaseCreate, CasePatch
from backend.services import classification
from backend.services import evidence as evidence_service
from backend.services import taxonomy as tx
from backend.services.audit import record_audit
from backend.services.geo import bbox_around, geometry_contains, haversine_m
from backend.services.notifications import notify
from backend.services.workflow import PRE_PROCESSING, add_event, transition

RECURRENCE_RADIUS_M = 150.0
RECURRENCE_WINDOW_DAYS = 240
EXCLUDED_FROM_SUPPORT = frozenset({"REJECTED"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------------------------------------ visibility
def visibility_clause(user: User):
    """SQL predicate of the cases ``user`` may see, ``True`` for all, or raises for roles that only get aggregates (§51A.18)."""
    r = user.role
    if r in CITY_WIDE_ROLES:
        return True
    if r == "citizen":
        return or_(CivicCase.reporter_id == user.id, exists().where(and_(Support.case_id == CivicCase.id, Support.user_id == user.id)))
    if r == "field_worker":
        return or_(CivicCase.reporter_id == user.id, exists().where(and_(WorkOrder.case_id == CivicCase.id, WorkOrder.assigned_worker_id == user.id)))
    if r in DEPARTMENT_ROLES:
        if not user.department_id:
            return CivicCase.id == None  # noqa: E711  (deny by default: no department, no cases)
        return or_(CivicCase.department_id == user.department_id, CivicCase.department_id.is_(None))
    if r == "ward_officer":
        return CivicCase.ward_id == user.ward_id if user.ward_id else (CivicCase.id == None)  # noqa: E711
    raise forbidden("Your role sees aggregated data only.", capability="view_cases")


def case_visible(db: Session, user: User, case: CivicCase) -> bool:
    try:
        clause = visibility_clause(user)
    except CivicConnectException:
        return False
    if clause is True:
        return True
    return db.execute(select(CivicCase.id).where(CivicCase.id == case.id, clause)).first() is not None


def get_visible_case(db: Session, user: User, case_id: str) -> CivicCase:
    """404 (not 403) when the case is not visible: callers cannot probe for the existence of other people's cases."""
    case = db.get(CivicCase, case_id)
    if case is None or not case_visible(db, user, case):
        raise CivicConnectException("CASE_NOT_FOUND", "The requested civic case does not exist.", 404)
    return case


def require_staff_scope(db: Session, user: User, case_id: str) -> CivicCase:
    if user.role not in STAFF_ROLES:
        raise forbidden()
    return get_visible_case(db, user, case_id)


# ------------------------------------------------------------------------------------------------ creation
def next_case_number(db: Session, year: int) -> str:
    row = db.execute(select(CaseCounter).where(CaseCounter.year == year).with_for_update()).scalar_one_or_none()
    if row is None:
        row = CaseCounter(year=year, last=0)
        db.add(row)
        db.flush()
    row.last += 1
    db.flush()
    return f"CC-{year}-{row.last:06d}"


def find_ward(db: Session, lat: float, lon: float) -> str | None:
    for w in db.execute(select(Ward)).scalars():
        if geometry_contains(w.boundary, lat, lon):
            return w.id
    return None


def recurrence_for(db: Session, lat: float, lon: float, category: str, subcategory: str | None, exclude_id: str | None = None) -> int:
    """Earlier cases of the same kind within ~150 m in the last ~8 months (design §38: the same problem keeps coming back)."""
    lo_lat, lo_lon, hi_lat, hi_lon = bbox_around(lat, lon, RECURRENCE_RADIUS_M)
    q = select(CivicCase).where(CivicCase.latitude.between(lo_lat, hi_lat), CivicCase.longitude.between(lo_lon, hi_lon), CivicCase.category == category,
                                CivicCase.created_at >= _now() - timedelta(days=RECURRENCE_WINDOW_DAYS), CivicCase.status != "REJECTED")
    if subcategory:
        q = q.where(CivicCase.subcategory == subcategory)
    if exclude_id:
        q = q.where(CivicCase.id != exclude_id)
    return sum(1 for c in db.execute(q).scalars() if haversine_m((lat, lon), (c.latitude, c.longitude)) <= RECURRENCE_RADIUS_M)


def active_incident_for(db: Session, case: CivicCase) -> bool:
    from backend.models import Incident, IncidentCase
    return db.execute(select(IncidentCase.case_id).join(Incident, Incident.id == IncidentCase.incident_id)
                      .where(IncidentCase.case_id == case.id, Incident.status == "ACTIVE")).first() is not None


def apply_assessment(db: Session, case: CivicCase) -> None:
    """(Re)compute severity / priority / SLA from the deterministic §36 rules. Never touches a human-decided case's department."""
    age_h = max(0.0, (_now() - case.created_at).total_seconds() / 3600.0)
    a = tx.assess(case.category or "other", case.subcategory, case.description or case.title, support_count=case.support_count, age_hours=age_h,
                  recurrence_count=case.recurrence_count, location_tags=list(case.location_tags or []), incident_active=active_incident_for(db, case))
    case.severity, case.priority, case.priority_score = a.severity, a.priority, a.score
    case.sla_class, case.sla_hours = a.sla_class, a.sla_hours
    case.sla_deadline = case.created_at + timedelta(hours=a.sla_hours)


def create_case(db: Session, user: User, body: CaseCreate) -> tuple[CivicCase, bool]:
    """Returns (case, created). A repeated ``client_case_id`` of the same reporter returns the existing case (offline retries never duplicate)."""
    if body.client_case_id:
        found = db.execute(select(CivicCase).where(CivicCase.reporter_id == user.id, CivicCase.client_case_id == body.client_case_id)).scalar_one_or_none()
        if found is not None:
            return found, False
    if not (body.title or body.description or body.evidence_ids):
        raise CivicConnectException("VALIDATION_ERROR", "A case needs a title, a description or evidence.", 422, {"fields": ["title", "description", "evidence_ids"]})
    category, subcategory = tx.resolve_category(body.category, body.subcategory)
    suggestion = None
    if not (body.category and body.category.strip()):            # a category given by a human is never replaced; only a missing one is suggested
        suggestion = classification.suggest("\n".join(x for x in (body.title, body.description) if x and x.strip()))
        if suggestion.applied:
            category, subcategory = suggestion.category, suggestion.subcategory
    now = _now()
    lat, lon = body.location.latitude, body.location.longitude
    case = CivicCase(id=new_id(), support_count=0, reopen_count=0, recurrence_count=0, location_tags=[], priority_score=0, case_number=next_case_number(db, now.year), client_case_id=body.client_case_id, title=(body.title or (body.description or "")[:80] or "Civic issue report"),
                     description=body.description, category=category, subcategory=subcategory, latitude=lat, longitude=lon, accuracy_m=body.location.accuracy_m,
                     ward_id=find_ward(db, lat, lon), department_id=tx.taxonomy().department_for(category, subcategory), reporter_id=user.id, language=body.language,
                     source=body.source, observed_at=body.observed_at, status="SUBMITTED", created_at=now, updated_at=now)
    case.recurrence_count = recurrence_for(db, lat, lon, category, subcategory)
    apply_assessment(db, case)
    db.add(case)
    try:
        db.flush()
    except IntegrityError:                                       # two retries raced on client_case_id
        db.rollback()
        found = db.execute(select(CivicCase).where(CivicCase.reporter_id == user.id, CivicCase.client_case_id == body.client_case_id)).scalar_one_or_none()
        if found is None:
            raise
        return found, False
    from backend.models import ReportSignal
    db.add(ReportSignal(case_id=case.id, reporter_id=user.id, original_text=body.description or body.title, original_language=body.language, is_primary=True,
                        latitude=lat, longitude=lon, source_type="SMARTPHONE"))
    add_event(db, case.id, "CASE_CREATED", actor_id=user.id, actor_role=user.role, metadata={"case_number": case.case_number, "source": body.source})
    if suggestion is not None:
        classification.record(db, case, suggestion)
    if body.evidence_ids:
        evidence_service.attach(db, user, body.evidence_ids, case, purpose="REPORT")
    # SUBMITTED -> AI_PROCESSING -> NEEDS_REVIEW: the deterministic assessment above already ran; the model-based enrichment (fusion / triage suggestion)
    # is queued and arrives as AIAnalysis rows the operator sees in the triage panel. The case never waits on a model.
    transition(db, case, "AI_PROCESSING", actor_id=None, actor_role="SYSTEM", notify_reporter=False)
    _queue_ai_enrichment(db, case)
    transition(db, case, "NEEDS_REVIEW", actor_id=None, actor_role="SYSTEM", notify_reporter=False)
    return case, True


def _queue_ai_enrichment(db: Session, case: CivicCase) -> None:
    """Queue the AI jobs once the case is COMMITTED (a worker that read it earlier would not find it). A rolled-back request queues nothing."""
    from sqlalchemy import event

    from backend.models import EvidenceItem
    case_id, number = case.id, case.case_number
    has_audio = db.execute(select(EvidenceItem.id).where(EvidenceItem.case_id == case_id, EvidenceItem.media_type == "AUDIO").limit(1)).first() is not None
    # order matters (one worker, in order): speech-to-text first (the transcript is case text), then the embedding (AI-2 compares vectors), then triage and fusion
    jobs = (["transcribe"] if has_audio else []) + ["embed", "triage", "fusion"]

    def _emit(_session) -> None:
        try:
            from backend.events import emit_ai_job
            for job in jobs:
                emit_ai_job(job, case_id, None, {"case_number": number})
        except Exception:
            pass                                                  # events are optional infrastructure
    event.listen(db, "after_commit", _emit, once=True)


# ------------------------------------------------------------------------------------------------ listing
SORTS = {"newest": [(CivicCase.created_at, True), (CivicCase.id, True)], "-created_at": [(CivicCase.created_at, True), (CivicCase.id, True)],
         "oldest": [(CivicCase.created_at, False), (CivicCase.id, False)], "created_at": [(CivicCase.created_at, False), (CivicCase.id, False)],
         "priority": [(CivicCase.priority_score, True), (CivicCase.created_at, True), (CivicCase.id, True)]}


def list_cases(db: Session, user: User, *, status: str | None = None, category: str | None = None, priority: str | None = None, ward_id: str | None = None,
               department_id: str | None = None, q: str | None = None, from_: datetime | None = None, until: datetime | None = None, sort: str | None = None,
               cursor: str | None = None, limit: int | None = None) -> tuple[list[CivicCase], str | None]:
    clause = visibility_clause(user)
    query = db.query(CivicCase)
    if clause is not True:
        query = query.filter(clause)
    if status:
        query = query.filter(CivicCase.status.in_([s.strip().upper() for s in status.split(",") if s.strip()]))
    if category:
        query = query.filter(CivicCase.category == category)
    if priority:
        query = query.filter(CivicCase.priority.in_([p.strip().upper() for p in priority.split(",") if p.strip()]))
    if ward_id:
        query = query.filter(CivicCase.ward_id == ward_id)
    if department_id:
        query = query.filter(CivicCase.department_id == department_id)
    if from_:
        query = query.filter(CivicCase.created_at >= from_)
    if until:
        query = query.filter(CivicCase.created_at <= until)
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(or_(CivicCase.case_number.ilike(like), CivicCase.title.ilike(like), CivicCase.description.ilike(like)))
    key = (sort or "newest")
    if key not in SORTS:
        raise CivicConnectException("VALIDATION_ERROR", "Unknown sort.", 422, {"field": "sort", "allowed": sorted(SORTS)})
    order = SORTS[key]
    fields = [c.key for c, _ in order]
    rows, nxt = paginate(query, order, cursor, clamp_limit(limit), lambda c: [getattr(c, f) for f in fields])
    annotate_flags(db, user, rows)
    return rows, nxt


# ------------------------------------------------------------------------------------------------ edits
CITIZEN_FIELDS = {"title", "description", "category", "subcategory"}
STAFF_FIELDS = CITIZEN_FIELDS | {"severity", "priority", "ward_id", "department_id"}
READ_ONLY = {"id", "case_number", "status", "created_at", "updated_at", "closed_at", "location", "support_count", "reopen_count", "sla_hours", "sla_deadline"}


def patch_case(db: Session, user: User, case: CivicCase, body: CasePatch) -> CivicCase:
    sent = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k in CasePatch.model_fields}      # extras are handled below
    reason = sent.pop("reason", None)
    extra = dict(body.model_extra or {})
    for k, v in extra.items():
        if k in READ_ONLY and getattr(case, k, None) is not None and _same(getattr(case, k), v):
            continue                                              # a client echoing back the whole object is fine
        raise CivicConnectException("FIELD_NOT_PERMITTED", f"'{k}' cannot be changed here.", 422, {"field": k})
    staff = user.role in STAFF_ROLES
    allowed = STAFF_FIELDS if staff else CITIZEN_FIELDS
    if not staff:
        if case.reporter_id != user.id:
            raise forbidden("Only the reporter may edit this case.")
        if case.status not in PRE_PROCESSING:
            raise CivicConnectException("CASE_NOT_EDITABLE", "The case can no longer be edited by the reporter.", 409, {"status": case.status})
    changes: dict[str, tuple[Any, Any]] = {}
    for k, v in sent.items():
        if k not in allowed:
            raise forbidden(f"Your role may not change '{k}'.", field=k)
        if v == getattr(case, k):
            continue
        changes[k] = (getattr(case, k), v)
    if not changes:
        annotate_flags(db, user, [case])
        return case
    if ("category" in changes or "subcategory" in changes):
        cat, sub = tx.resolve_category(changes.get("category", (None, case.category))[1], changes.get("subcategory", (None, case.subcategory))[1])
        changes["category"], changes["subcategory"] = (case.category, cat), (case.subcategory, sub)
    if "department_id" in changes:
        from backend.models import Department
        if changes["department_id"][1] is not None and db.get(Department, changes["department_id"][1]) is None:
            raise CivicConnectException("DEPARTMENT_UNKNOWN", "Unknown department.", 422, {"department_id": changes["department_id"][1]})
    if "ward_id" in changes and changes["ward_id"][1] is not None and db.get(Ward, changes["ward_id"][1]) is None:
        raise CivicConnectException("WARD_UNKNOWN", "Unknown ward.", 422, {"ward_id": changes["ward_id"][1]})
    overrides = {k for k in ("category", "subcategory", "priority", "severity", "department_id") if k in changes}
    if staff and overrides and not (reason and reason.strip()):
        raise CivicConnectException("REASON_REQUIRED", "Overriding category, severity, priority or department needs a reason (it is audited).", 422, {"field": "reason"})
    for k, (_, new) in changes.items():
        setattr(case, k, new)
    case.updated_at = _now()
    before = {k: old for k, (old, _) in changes.items()}
    after = {k: new for k, (_, new) in changes.items()}
    if staff and overrides:
        action = "CATEGORY_OVERRIDDEN" if {"category", "subcategory"} & overrides else ("PRIORITY_OVERRIDDEN" if "priority" in overrides else "CASE_FIELDS_OVERRIDDEN")
        record_audit(db, actor_id=user.id, action=action, entity_type="CIVIC_CASE", entity_id=case.id, before=before, after={**after, "reason": reason})
    add_event(db, case.id, "CASE_UPDATED", actor_id=user.id, actor_role=user.role, metadata={"fields": sorted(after)}, visibility="PUBLIC" if not staff else "INTERNAL")
    db.flush()
    annotate_flags(db, user, [case])
    return case


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, datetime) and isinstance(b, str):
        try:
            return a == datetime.fromisoformat(b.replace("Z", "+00:00"))
        except ValueError:
            return False
    return a == b


# ------------------------------------------------------------------------------------------------ support / contributors
def add_support(db: Session, user: User, case: CivicCase, role: str = "SUPPORTER") -> tuple[Support, bool]:
    if case.status in EXCLUDED_FROM_SUPPORT:
        raise CivicConnectException("CASE_CLOSED", "This case was rejected.", 409)
    existing = db.execute(select(Support).where(Support.case_id == case.id, Support.user_id == user.id)).scalar_one_or_none()
    if existing:
        if role == "CONTRIBUTOR" and existing.role != "CONTRIBUTOR":
            existing.role = "CONTRIBUTOR"
        return existing, False
    s = Support(case_id=case.id, user_id=user.id, role=role)
    db.add(s)
    case.support_count = (case.support_count or 0) + (1 if role == "SUPPORTER" else 0)
    if role == "SUPPORTER":
        apply_assessment(db, case)                                # support count is one of the §36 priority inputs
    case.updated_at = _now()
    db.flush()
    add_event(db, case.id, "SUPPORT_ADDED", actor_id=user.id, actor_role=user.role, metadata={"support_count": case.support_count})
    return s, True


def remove_support(db: Session, user: User, case: CivicCase) -> bool:
    s = db.execute(select(Support).where(Support.case_id == case.id, Support.user_id == user.id, Support.role == "SUPPORTER")).scalar_one_or_none()
    if not s:
        return False
    db.delete(s)
    case.support_count = max(0, (case.support_count or 0) - 1)
    apply_assessment(db, case)
    db.flush()
    add_event(db, case.id, "SUPPORT_REMOVED", actor_id=user.id, actor_role=user.role, metadata={"support_count": case.support_count})
    return True


def add_contributor(db: Session, actor: User, case: CivicCase, user_id: str) -> Support:
    if not (actor.role in STAFF_ROLES or case.reporter_id == actor.id):
        raise forbidden("Only the reporter or staff may add contributors.")
    target = db.get(User, user_id)
    if target is None or not target.is_active:
        raise CivicConnectException("USER_NOT_FOUND", "That user does not exist.", 404)
    s, _ = add_support(db, target, case, role="CONTRIBUTOR")
    notify(db, [target.id], "CASE_UPDATED", {"case_id": case.id, "case_number": case.case_number, "title": f"You were added to case {case.case_number}", "message": ""},
           template="case.contributor_added", params={"case_number": case.case_number})
    return s


# ------------------------------------------------------------------------------------------------ serialization
def location_of(c: CivicCase) -> dict:
    return {"latitude": c.latitude, "longitude": c.longitude, "accuracy_m": c.accuracy_m}


def annotate_flags(db: Session, user: User, cases: list[CivicCase]) -> None:
    """Staff views carry ``open_flag_count`` / ``needs_flag_review`` / ``map_hidden`` (one grouped count for the whole page); everyone else gets the defaults."""
    from backend.services import flags as flag_service
    flag_service.annotate_cases(db, user, cases)


def view_case(db: Session, user: User, c: CivicCase) -> dict:
    """``serialize_case`` with the caller's flag fields (for single-case responses)."""
    annotate_flags(db, user, [c])
    return serialize_case(c)


def serialize_case(c: CivicCase) -> dict:
    n, review, hidden = getattr(c, "_flag_view", (0, False, False))
    return {"open_flag_count": n, "needs_flag_review": review, "map_hidden": hidden, "id": c.id, "case_number": c.case_number, "title": c.title, "description": c.description, "status": c.status, "category": c.category,
            "subcategory": c.subcategory, "severity": c.severity, "priority": c.priority, "location": location_of(c), "ward_id": c.ward_id, "department_id": c.department_id,
            "support_count": c.support_count, "reopen_count": c.reopen_count, "sla_hours": c.sla_hours, "sla_deadline": c.sla_deadline, "created_at": c.created_at,
            "updated_at": c.updated_at, "closed_at": c.closed_at}


def serialize_detail(db: Session, user: User, c: CivicCase) -> dict:
    from backend.services import timeline as timeline_service
    staff = user.role in STAFF_ROLES
    annotate_flags(db, user, [c])
    out = serialize_case(c)
    out["is_reporter"] = c.reporter_id == user.id
    out["contributors"] = db.execute(select(func.count()).select_from(Support).where(Support.case_id == c.id, Support.role == "CONTRIBUTOR")).scalar_one()
    reporter = db.get(User, c.reporter_id) if (staff and c.reporter_id) else None
    out["reporter"] = {"id": reporter.id, "name": reporter.name} if reporter else None
    evs = [e for e in evidence_service.list_for_case(db, c.id) if evidence_service.can_view(db, user, e)]
    out["evidence"] = [evidence_service.serialize(e, with_location=staff) for e in evs]
    wos = db.execute(select(WorkOrder).where(WorkOrder.case_id == c.id).order_by(WorkOrder.created_at)).scalars().all()
    out["work_orders"] = [{"id": w.id, "status": w.status, "priority": w.priority, "due_at": w.deadline, "started_at": w.started_at, "completed_at": w.completed_at,
                           **({"assignee_id": w.assigned_worker_id, "instructions": w.instructions} if staff or user.role == "field_worker" else {})} for w in wos]
    out["timeline"] = [timeline_service.serialize(e, staff=staff) for e in timeline_service.events_for(db, user, c.id, limit=50)[0]]
    return out
