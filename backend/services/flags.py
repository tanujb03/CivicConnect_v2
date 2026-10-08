"""Community flags on cases (WP4): citizens flag a case (still exists / outdated / incorrect / inappropriate), staff resolve the flags.

The number of OPEN flags is derived at read time (never stored): at ``flag_review_threshold`` (system setting, default 3) the case "needs flag review" and staff are told.
A case is hidden from the non-staff map while it has open ``INAPPROPRIATE`` flags at the threshold, or once staff UPHELD an ``INAPPROPRIATE`` flag on it.
"""
from __future__ import annotations

from sqlalchemy import case, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.exceptions import CivicConnectException
from backend.core.permissions import DEPARTMENT_ROLES, STAFF_ROLES, forbidden
from backend.models import FLAG_KINDS, FLAG_STATUSES, CaseEvent, CaseFlag, CivicCase, SystemSetting, User
from backend.schemas.platform import CaseFlagIn, CaseFlagResolveIn
from backend.services import cases as case_service
from backend.services.audit import record_audit
from backend.services.notifications import notify
from backend.services.workflow import add_event, utcnow

THRESHOLD_KEY = "flag_review_threshold"
DEFAULT_THRESHOLD = 3


def review_threshold(db: Session) -> int:
    """The admin setting ``flag_review_threshold`` (1 to 100); the default when unset or unreadable."""
    row = db.get(SystemSetting, THRESHOLD_KEY)
    v = row.value_json if row is not None else DEFAULT_THRESHOLD
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 1 else DEFAULT_THRESHOLD


def open_count(db: Session, case_id: str) -> int:
    return db.execute(select(func.count()).select_from(CaseFlag).where(CaseFlag.case_id == case_id, CaseFlag.status == "OPEN")).scalar_one()


def _states(db: Session, case_ids: list[str], threshold: int) -> dict[str, tuple[int, bool, bool]]:
    """``case_id -> (open flags, needs_flag_review, map_hidden)`` for cases that have open or UPHELD flags, in ONE grouped query (list views must not query per row)."""
    rows = db.execute(select(CaseFlag.case_id, CaseFlag.kind, CaseFlag.status, func.count()).where(CaseFlag.case_id.in_(case_ids), CaseFlag.status.in_(("OPEN", "UPHELD")))
                      .group_by(CaseFlag.case_id, CaseFlag.kind, CaseFlag.status)).all()
    open_, inappropriate, upheld = {}, {}, set()
    for cid, kind, status, n in rows:
        if status == "OPEN":
            open_[cid] = open_.get(cid, 0) + n
            if kind == "INAPPROPRIATE":
                inappropriate[cid] = n
        elif kind == "INAPPROPRIATE":
            upheld.add(cid)
    return {cid: (n, n >= threshold, inappropriate.get(cid, 0) >= threshold or cid in upheld) for cid, n in open_.items()} | \
           {cid: (0, False, True) for cid in upheld if cid not in open_}


def annotate_cases(db: Session, user: User, cases: list[CivicCase]) -> None:
    """Stash ``(open_flag_count, needs_flag_review, map_hidden)`` on each case for ``serialize_case``. Staff only: citizens never learn about flags."""
    if user.role not in STAFF_ROLES or not cases:
        return
    states = _states(db, [c.id for c in cases], review_threshold(db))
    for c in cases:
        c._flag_view = states.get(c.id, (0, False, False))                   # type: ignore[attr-defined]  (transient, not a mapped column)


def map_hidden(db: Session, case_id: str) -> bool:
    return _states(db, [case_id], review_threshold(db)).get(case_id, (0, False, False))[2]


def hidden_from_public_map(db: Session):
    """Subquery of case ids hidden from the non-staff map: open INAPPROPRIATE flags at or above the threshold, or at least one UPHELD INAPPROPRIATE flag."""
    open_n = func.sum(case((CaseFlag.status == "OPEN", 1), else_=0))
    upheld_n = func.sum(case((CaseFlag.status == "UPHELD", 1), else_=0))
    return select(CaseFlag.case_id).where(CaseFlag.kind == "INAPPROPRIATE").group_by(CaseFlag.case_id).having(or_(open_n >= review_threshold(db), upheld_n >= 1))


def serialize(f: CaseFlag) -> dict:
    return {"id": f.id, "case_id": f.case_id, "kind": f.kind, "comment": f.comment, "status": f.status, "created_at": f.created_at, "resolved_at": f.resolved_at}


def _reviewers(db: Session, case_: CivicCase, exclude: str) -> list[str]:
    """Active operators and department managers of the case's department plus the officers of its ward; active city admins when there is nobody else."""
    def active(*conds) -> list[str]:
        return db.execute(select(User.id).where(User.is_active.is_(True), User.id != exclude, *conds)).scalars().all()
    ids: list[str] = []
    if case_.department_id:
        ids += active(User.role.in_(sorted(DEPARTMENT_ROLES)), User.department_id == case_.department_id)
    if case_.ward_id:
        ids += active(User.role == "ward_officer", User.ward_id == case_.ward_id)
    return list(dict.fromkeys(ids)) or active(User.role == "city_admin")


def _review_due(db: Session, case_id: str, n: int, threshold: int) -> bool:
    """Open flags at or above the threshold and no FLAG_REVIEW_REQUESTED newer than the latest FLAG_RESOLVED (or none at all): staff are told once per episode."""
    if n < threshold:
        return False

    def latest(event_type: str) -> int | None:
        return db.execute(select(func.max(CaseEvent.seq)).where(CaseEvent.case_id == case_id, CaseEvent.event_type == event_type)).scalar()
    requested, resolved = latest("FLAG_REVIEW_REQUESTED"), latest("FLAG_RESOLVED")
    return requested is None or (resolved is not None and requested < resolved)


def _already_flagged(db: Session, case_id: str, user_id: str, kind: str) -> bool:
    return db.execute(select(CaseFlag.id).where(CaseFlag.case_id == case_id, CaseFlag.user_id == user_id, CaseFlag.kind == kind)).first() is not None


# ------------------------------------------------------------------------------------------------ create
def create(db: Session, user: User, case_id: str, body: CaseFlagIn) -> CaseFlag:
    case_ = case_service.get_visible_case(db, user, case_id)                 # 404 when the caller may not see the case
    if body.kind == "INAPPROPRIATE" and case_.reporter_id == user.id:
        raise CivicConnectException("FLAG_NOT_ALLOWED", "You cannot flag your own report as inappropriate.", 403, {"kind": body.kind})
    dup = CivicConnectException("FLAG_ALREADY_EXISTS", "You can flag each reason on a case only once, even after your earlier flag was resolved.", 409, {"kind": body.kind})
    if _already_flagged(db, case_.id, user.id, body.kind):
        raise dup
    flag = CaseFlag(case_id=case_.id, user_id=user.id, kind=body.kind, comment=(body.comment or "").strip() or None, status="OPEN")
    try:
        with db.begin_nested():                                              # a concurrent duplicate is a clean 409, not an idempotency race
            db.add(flag)
            db.flush()
    except IntegrityError:
        raise dup from None
    record_audit(db, actor_id=user.id, action="case_flag.created", entity_type="CASE_FLAG", entity_id=flag.id, before=None,
                 after={"case_id": case_.id, "kind": flag.kind, "status": flag.status})
    n, threshold = open_count(db, case_.id), review_threshold(db)
    if _review_due(db, case_.id, n, threshold):
        hidden = map_hidden(db, case_.id)
        add_event(db, case_.id, "FLAG_REVIEW_REQUESTED", actor_id=None, actor_role="SYSTEM", visibility="INTERNAL",
                  metadata={"open_flags": n, "threshold": threshold, "map_hidden": hidden})
        notify(db, _reviewers(db, case_, exclude=user.id), "CASE_FLAG_REVIEW",
               {"case_id": case_.id, "case_number": case_.case_number, "title": f"Case {case_.case_number} needs a flag review",
                "message": f"Case {case_.case_number} has {n} open flag{'s' if n != 1 else ''} and needs a review." + (" It is hidden from the public map until the flags are resolved." if hidden else "")})
    return flag


# ------------------------------------------------------------------------------------------------ list / resolve
def list_for_case(db: Session, user: User, case_id: str) -> dict:
    if user.role not in STAFF_ROLES:
        raise forbidden("Only staff may list the flags of a case.")
    case_ = case_service.get_visible_case(db, user, case_id)
    rows = db.execute(select(CaseFlag).where(CaseFlag.case_id == case_.id).order_by(CaseFlag.created_at.desc(), CaseFlag.id)).scalars().all()
    by_kind, by_status = dict.fromkeys(FLAG_KINDS, 0), dict.fromkeys(FLAG_STATUSES, 0)
    for f in rows:
        by_kind[f.kind] += 1
        by_status[f.status] += 1
    return {"items": [serialize(f) for f in rows], "counts": {"by_kind": by_kind, "by_status": by_status}}


def resolve(db: Session, user: User, flag_id: str, body: CaseFlagResolveIn) -> CaseFlag:
    if user.role not in STAFF_ROLES:
        raise forbidden("Only staff may resolve flags.")
    flag = db.get(CaseFlag, flag_id)
    case_ = db.get(CivicCase, flag.case_id) if flag is not None else None
    if flag is None or case_ is None or not case_service.case_visible(db, user, case_):          # out of scope looks the same as unknown
        raise CivicConnectException("FLAG_NOT_FOUND", "The requested flag does not exist.", 404)
    if flag.user_id == user.id:
        raise CivicConnectException("FLAG_NOT_ALLOWED", "You cannot resolve a flag you raised yourself.", 403)
    done = db.execute(update(CaseFlag).where(CaseFlag.id == flag.id, CaseFlag.status == "OPEN")
                      .values(status=body.status, resolved_by=user.id, resolved_at=utcnow()).execution_options(synchronize_session=False))
    if done.rowcount != 1:                                                   # somebody resolved it between the read and the write
        raise CivicConnectException("FLAG_ALREADY_RESOLVED", "This flag was already resolved.", 409)
    db.refresh(flag)
    n, threshold = open_count(db, case_.id), review_threshold(db)
    record_audit(db, actor_id=user.id, action="case_flag.resolved", entity_type="CASE_FLAG", entity_id=flag.id, before={"status": "OPEN"},
                 after={"case_id": case_.id, "kind": flag.kind, "status": flag.status})
    add_event(db, case_.id, "FLAG_RESOLVED", actor_id=user.id, actor_role=user.role, visibility="INTERNAL",
              metadata={"flag_id": flag.id, "kind": flag.kind, "status": flag.status, "open_flags": n, "review_cleared": n == threshold - 1})
    return flag
