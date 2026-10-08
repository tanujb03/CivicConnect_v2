"""User management for administrators (A12, design §46): list, create staff with a one-time password, change role / department / ward / active.

Rules (all enforced here, not in the client):
* Elevated roles (CITY_ADMIN, SYSTEM_ADMIN; the design's SUPER_ADMIN is the code's SYSTEM_ADMIN) can only be granted, changed or deactivated by a SYSTEM_ADMIN.
* OPERATOR / DEPARTMENT_MANAGER / FIELD_WORKER need a department, WARD_OFFICER needs a ward, every other role has neither.
* Nobody changes their own role or deactivates themselves (no self-lockout).
* Deactivating ends all sessions at once: ``current_user`` already rejects an inactive account on the next request, and the refresh and push-device tokens are revoked here.
* Every change writes AuditEvent rows with before/after; passwords (and their hashes) are never audited.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.exceptions import CivicConnectException
from backend.core.pagination import clamp_limit, paginate
from backend.core.permissions import ALL_ROLES, forbidden
from backend.core.security import get_password_hash
from backend.models import CivicCase, Department, DeviceToken, RefreshToken, User, Ward
from backend.schemas.admin import UserCreateIn
from backend.services.audit import record_audit
from backend.services.auth import revoke_all_refresh

ELEVATED_ROLES = frozenset({"city_admin", "system_admin"})
ASSIGNABLE_ON_CREATE = ALL_ROLES - {"citizen"}                      # citizens register themselves
DEPARTMENT_SCOPED = frozenset({"operator", "department_manager", "field_worker"})
WARD_SCOPED = frozenset({"ward_officer"})
AUDITED_FIELDS = ("name", "email", "phone", "role", "department_id", "ward_id", "is_active", "preferred_language")


def _invalid(field: str, message: str) -> CivicConnectException:
    return CivicConnectException("VALIDATION_ERROR", message, 422, {"field": field})


def _role(value: str, *, creating: bool) -> str:
    role = value.strip().lower()
    allowed = ASSIGNABLE_ON_CREATE if creating else ALL_ROLES
    if role not in allowed:
        raise _invalid("role", f"role must be one of: {', '.join(sorted(r.upper() for r in allowed))}.")
    return role


def _grant_check(actor: User, role: str) -> None:
    if role in ELEVATED_ROLES and actor.role != "system_admin":
        raise forbidden("Only a SYSTEM_ADMIN may grant or change an elevated role.", capability="grant_elevated_role", role=role.upper())


def _scope(db: Session, role: str, department_id: str | None, ward_id: str | None) -> tuple[str | None, str | None]:
    dept, ward = department_id or None, ward_id or None
    label = role.upper()
    if role in DEPARTMENT_SCOPED:
        if not dept:
            raise _invalid("department_id", f"{label} needs a department_id.")
        if db.get(Department, dept) is None:
            raise _invalid("department_id", "That department does not exist.")
        if ward:
            raise _invalid("ward_id", f"ward_id must be empty for {label}.")
    elif role in WARD_SCOPED:
        if not ward:
            raise _invalid("ward_id", f"{label} needs a ward_id.")
        if db.get(Ward, ward) is None:
            raise _invalid("ward_id", "That ward does not exist.")
        if dept:
            raise _invalid("department_id", f"department_id must be empty for {label}.")
    else:
        if dept:
            raise _invalid("department_id", f"department_id must be empty for {label}.")
        if ward:
            raise _invalid("ward_id", f"ward_id must be empty for {label}.")
    return dept, ward


def snapshot(user: User) -> dict[str, Any]:
    return {f: getattr(user, f) for f in AUDITED_FIELDS}


def to_out(user: User, cases_reported: int = 0) -> dict[str, Any]:
    return {"id": user.id, "name": user.name, "email": user.email, "phone": user.phone, "role": user.role.upper(), "department_id": user.department_id, "ward_id": user.ward_id,
            "preferred_language": user.preferred_language, "is_active": user.is_active, "status": "active" if user.is_active else "inactive", "synthetic": user.synthetic,
            "created_at": user.created_at, "updated_at": user.updated_at, "last_login_at": user.last_login_at, "cases_reported": cases_reported,
            "must_change_password": bool(user.must_change_password)}


def _reported_counts(db: Session, ids: list[str]) -> dict[str, int]:
    if not ids:
        return {}
    return dict(db.execute(select(CivicCase.reporter_id, func.count()).where(CivicCase.reporter_id.in_(ids)).group_by(CivicCase.reporter_id)).all())


def _like(q: str) -> str:
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def list_users(db: Session, *, role: str | None, department_id: str | None, ward_id: str | None, is_active: bool | None, q: str | None, cursor: str | None,
               limit: int | None) -> tuple[list[dict[str, Any]], str | None]:
    query = db.query(User)
    if role:
        query = query.filter(User.role == _role(role, creating=False))
    if department_id:
        query = query.filter(User.department_id == department_id)
    if ward_id:
        query = query.filter(User.ward_id == ward_id)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    if q and q.strip():
        pat = _like(q.strip())
        query = query.filter(or_(User.name.ilike(pat, escape="\\"), User.email.ilike(pat, escape="\\"), User.phone.ilike(pat, escape="\\")))
    rows, nxt = paginate(query, [(User.created_at, True), (User.id, True)], cursor, clamp_limit(limit), lambda u: [u.created_at, u.id])
    counts = _reported_counts(db, [u.id for u in rows])
    return [to_out(u, counts.get(u.id, 0)) for u in rows], nxt


def get_or_404(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise CivicConnectException("USER_NOT_FOUND", "The user does not exist.", 404)
    return user


def create_user(db: Session, actor: User, body: UserCreateIn) -> tuple[User, str]:
    """Returns (user, temporary_password). The caller commits; the password is only returned, never stored in clear."""
    role = _role(body.role, creating=True)
    _grant_check(actor, role)
    if not body.email and not body.phone:
        raise CivicConnectException("VALIDATION_ERROR", "Give an email address or a phone number.", 422, {"fields": ["email", "phone"]})
    dept, ward = _scope(db, role, body.department_id, body.ward_id)
    clauses = ([User.email == body.email] if body.email else []) + ([User.phone == body.phone] if body.phone else [])
    if db.execute(select(User.id).where(or_(*clauses))).first():
        raise CivicConnectException("USER_ALREADY_EXISTS", "An account with that email or phone already exists.", 409)
    password = secrets.token_urlsafe(12)
    user = User(name=body.name.strip(), email=body.email, phone=body.phone, hashed_password=get_password_hash(password), role=role, department_id=dept, ward_id=ward,
                preferred_language=body.preferred_language, is_active=True, must_change_password=True)
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise CivicConnectException("USER_ALREADY_EXISTS", "An account with that email or phone already exists.", 409) from None
    record_audit(db, actor_id=actor.id, action="user.created", entity_type="user", entity_id=user.id, before=None, after=snapshot(user))
    return user, password


def _revoke_sessions(db: Session, user_id: str) -> None:
    now = datetime.now(timezone.utc)
    db.execute(update(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)).values(revoked_at=now))
    db.execute(update(DeviceToken).where(DeviceToken.user_id == user_id, DeviceToken.revoked_at.is_(None)).values(revoked_at=now))


def reset_password(db: Session, actor: User, user_id: str) -> tuple[User, str]:
    """Replaces the user's password with a generated one-time password (returned, never stored in clear), forces a change at the next sign-in and revokes
    their refresh tokens and (``password_changed_at`` = now) every access token issued before. Same elevated-role rule as ``update_user``; nobody resets their own password here (use ``/auth/change-password``). The caller commits."""
    target = get_or_404(db, user_id)
    if target.role in ELEVATED_ROLES and actor.role != "system_admin":
        raise forbidden("Only a SYSTEM_ADMIN may reset the password of a user with an elevated role.", capability="grant_elevated_role")
    if target.id == actor.id:
        raise CivicConnectException("CANNOT_MODIFY_SELF", "You cannot reset your own password here; use POST /auth/change-password.", 409)
    password, was_forced = secrets.token_urlsafe(12), target.must_change_password
    target.hashed_password, target.must_change_password, target.password_changed_at = get_password_hash(password), True, datetime.now(timezone.utc)     # old access tokens die now
    revoked = revoke_all_refresh(db, target.id)
    db.flush()
    record_audit(db, actor_id=actor.id, action="user.password_reset", entity_type="user", entity_id=target.id,
                 before={"must_change_password": was_forced}, after={"must_change_password": True, "sessions_revoked": revoked})
    return target, password


def update_user(db: Session, actor: User, user_id: str, patch: dict[str, Any]) -> User:
    """``patch`` holds only the fields the client sent (``model_dump(exclude_unset=True)``). Writes the changes and their audit rows; the caller commits."""
    target = get_or_404(db, user_id)
    if target.role in ELEVATED_ROLES and actor.role != "system_admin":
        raise forbidden("Only a SYSTEM_ADMIN may change a user with an elevated role.", capability="grant_elevated_role")
    for field in ("name", "role", "is_active"):
        if field in patch and patch[field] is None:
            raise _invalid(field, f"{field} cannot be null.")
    before = snapshot(target)
    new_role = _role(patch["role"], creating=False) if "role" in patch else target.role
    if new_role != target.role:
        _grant_check(actor, new_role)
    if target.id == actor.id and (new_role != target.role or patch.get("is_active") is False):
        raise CivicConnectException("CANNOT_MODIFY_SELF", "You cannot change your own role or deactivate your own account.", 409)
    if {"role", "department_id", "ward_id"} & set(patch):
        dept = patch["department_id"] if "department_id" in patch else target.department_id
        ward = patch["ward_id"] if "ward_id" in patch else target.ward_id
        if new_role != target.role:                          # a field that does not apply to the new role is cleared, unless the client set it explicitly
            dept = dept if "department_id" in patch or new_role in DEPARTMENT_SCOPED else None
            ward = ward if "ward_id" in patch or new_role in WARD_SCOPED else None
        target.department_id, target.ward_id = _scope(db, new_role, dept, ward)
    target.role = new_role
    if "name" in patch:
        target.name = patch["name"].strip()
    if "is_active" in patch:
        target.is_active = bool(patch["is_active"])
    db.flush()
    after = snapshot(target)
    changed = {k for k in AUDITED_FIELDS if before[k] != after[k]}
    if not changed:
        return target

    def audit(action: str, keys: set[str]) -> None:
        if keys:
            record_audit(db, actor_id=actor.id, action=action, entity_type="user", entity_id=target.id,
                         before={k: before[k] for k in sorted(keys)}, after={k: after[k] for k in sorted(keys)})

    role_keys = {"role"} | ({"department_id", "ward_id"} & changed) if "role" in changed else set()
    audit("user.role_changed", role_keys)
    if "is_active" in changed:
        audit("user.deactivated" if not target.is_active else "user.reactivated", {"is_active"})
        if not target.is_active:
            _revoke_sessions(db, target.id)
    audit("user.updated", changed - role_keys - {"is_active"})
    return target


def cases_reported(db: Session, user_id: str) -> int:
    return _reported_counts(db, [user_id]).get(user_id, 0)
