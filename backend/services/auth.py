"""Accounts, sessions and profile (§51A.2, §51A.3)."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.exceptions import CivicConnectException
from backend.core.permissions import CAPABILITIES, CITY_WIDE_ROLES
from backend.core.rate_limit import FailureCounter
from backend.core.security import create_access_token, get_password_hash, hash_refresh_token, new_refresh_token, verify_password
from backend.models import RefreshToken, User
from backend.schemas.auth import ProfilePatch, RegisterIn
from backend.services.audit import record_audit

MIN_PASSWORD_LENGTH = 10
COMMON_PASSWORDS = frozenset({"password", "password1", "password123", "passw0rd", "1234567890", "12345678", "123456789", "qwertyuiop", "qwerty123", "qwerty", "letmein123",
                              "iloveyou", "welcome123", "admin12345", "changeme123", "abcdefghij", "civicconnect", "civicconnect1"})
_DUMMY_HASH = get_password_hash("not-a-real-password")      # verified against when the account does not exist (no user-enumeration by timing)
MAX_FAILURES, LOCK_SECONDS = 5, 60
_counter = FailureCounter(window_s=LOCK_SECONDS, namespace="signin")
_pw_counter = FailureCounter(window_s=LOCK_SECONDS, namespace="pwchange")     # its own namespace: a crafted sign-in identifier can never lock a password change       # WP3: sliding window in Redis (shared by all workers), in-process fallback when Redis is down


def _normalize_identifier(identifier: str) -> tuple[str | None, str | None]:
    ident = identifier.strip()
    if "@" in ident:
        return ident.lower(), None
    return None, "".join(ch for ch in ident if ch.isdigit() or ch == "+")


def _throttle_check(key: str, now: float | None = None, counter: FailureCounter | None = None) -> None:
    counter = counter or _counter
    if counter.count(key) >= MAX_FAILURES:
        retry = max(1, counter.retry_after(key))
        raise CivicConnectException("RATE_LIMITED", "Too many failed attempts. Try again in a minute.", 429, {"retry_after_seconds": retry}, headers={"Retry-After": str(retry)})


def reset_throttle() -> None:
    _counter.reset()
    _pw_counter.reset()


def session_for(db: Session, user: User) -> dict:
    refresh, digest = new_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=digest, expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)))
    db.flush()
    return {"user": brief(user), "access_token": create_access_token(user.id, user.role), "refresh_token": refresh, "token_type": "bearer"}


def brief(user: User) -> dict:
    return {"id": user.id, "name": user.name, "role": user.role.upper(), "must_change_password": bool(user.must_change_password)}


def register(db: Session, body: RegisterIn) -> User:
    if not body.email and not body.phone:
        raise CivicConnectException("VALIDATION_ERROR", "Give an email address or a phone number.", 422, {"fields": ["email", "phone"]})
    clauses = [User.email == body.email] if body.email else []
    if body.phone:
        clauses.append(User.phone == body.phone)
    if db.execute(select(User.id).where(or_(*clauses))).first():
        raise CivicConnectException("USER_ALREADY_EXISTS", "An account with that email or phone already exists.", 409)
    user = User(name=body.name.strip(), email=body.email, phone=body.phone, hashed_password=get_password_hash(body.password), role="citizen", preferred_language=body.preferred_language)
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise CivicConnectException("USER_ALREADY_EXISTS", "An account with that email or phone already exists.", 409)
    return user


def authenticate(db: Session, identifier: str, password: str, now: float | None = None) -> User:
    now = now if now is not None else time.time()
    key = identifier.strip().lower()
    _throttle_check(key, now)
    email, phone = _normalize_identifier(identifier)
    q = select(User).where(User.email == email) if email else select(User).where(User.phone == phone)
    user = db.execute(q).scalar_one_or_none()
    ok = verify_password(password, user.hashed_password if user else _DUMMY_HASH)
    if not (user and ok and user.is_active):
        _counter.add(key)
        raise CivicConnectException("AUTH_INVALID_CREDENTIALS", "Incorrect identifier or password.", 401)
    _counter.clear(key)
    user.last_login_at = datetime.now(timezone.utc)
    return user


def rotate_refresh(db: Session, token: str) -> tuple[User, dict]:
    row = db.execute(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token))).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if row is None or row.expires_at < now:
        raise CivicConnectException("AUTH_INVALID_TOKEN", "The refresh token is invalid or expired.", 401)
    if row.revoked_at is not None:                       # a used token came back: assume it leaked and end every session of that user
        for t in db.execute(select(RefreshToken).where(RefreshToken.user_id == row.user_id, RefreshToken.revoked_at.is_(None))).scalars():
            t.revoked_at = now
        db.commit()
        raise CivicConnectException("AUTH_INVALID_TOKEN", "The refresh token was already used; sign in again.", 401)
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise CivicConnectException("AUTH_INVALID_TOKEN", "The account no longer exists or is inactive.", 401)
    row.revoked_at = now
    return user, session_for(db, user)


def revoke_refresh(db: Session, token: str) -> None:
    row = db.execute(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token))).scalar_one_or_none()
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)


def revoke_all_refresh(db: Session, user_id: str) -> int:
    """Revokes every live refresh token of the user (password change / reset); returns how many."""
    res = db.execute(update(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)).values(revoked_at=datetime.now(timezone.utc)))
    return res.rowcount or 0


def check_password_policy(new_password: str, current_password: str) -> None:
    """Minimum 10 characters, not the current password, not an obvious one (small deny-list, plus the demo password). Raises 422 ``WEAK_PASSWORD``."""
    reasons: list[str] = []
    if len(new_password) < MIN_PASSWORD_LENGTH:
        reasons.append(f"at least {MIN_PASSWORD_LENGTH} characters")
    if new_password == current_password:
        reasons.append("different from the current password")
    if new_password.strip().lower() in COMMON_PASSWORDS | {settings.DEMO_PASSWORD.lower()} or len(set(new_password)) == 1:
        reasons.append("not a commonly used password")
    if reasons:
        raise CivicConnectException("WEAK_PASSWORD", "The new password is not acceptable: it must be " + ", ".join(reasons) + ".", 422, {"field": "new_password", "reasons": reasons})


def change_password(db: Session, user: User, current_password: str, new_password: str, now: float | None = None) -> dict:
    """Verifies the current password (throttled per user), applies the policy, stores the new hash, revokes every refresh token and returns a fresh session.
    The caller commits. Only metadata is audited, never a password or hash."""
    now = now if now is not None else time.time()
    key = user.id
    _throttle_check(key, now, _pw_counter)
    if not verify_password(current_password, user.hashed_password):
        _pw_counter.add(key)
        raise CivicConnectException("CURRENT_PASSWORD_INCORRECT", "The current password is incorrect.", 400)
    _pw_counter.clear(key)
    check_password_policy(new_password, current_password)
    was_forced, changed_at = user.must_change_password, datetime.now(timezone.utc)
    user.hashed_password, user.password_changed_at, user.must_change_password = get_password_hash(new_password), changed_at, False
    revoked = revoke_all_refresh(db, user.id)
    record_audit(db, actor_id=user.id, action="user.password_changed", entity_type="user", entity_id=user.id,
                 before={"must_change_password": was_forced}, after={"must_change_password": False, "password_changed_at": changed_at.isoformat(), "sessions_revoked": revoked})
    return session_for(db, user)


def access_scope(user: User) -> dict:
    return {"role": user.role.upper(), "city_wide": user.role in CITY_WIDE_ROLES, "department_id": user.department_id, "ward_id": user.ward_id,
            "capabilities": sorted(name for name, roles in CAPABILITIES.items() if user.role in roles)}


def profile(user: User) -> dict:
    return {"id": user.id, "name": user.name, "role": user.role.upper(), "email": user.email, "phone": user.phone, "preferred_language": user.preferred_language,
            "accessibility": user.accessibility or {}, "department_id": user.department_id, "ward_id": user.ward_id, "access_scope": access_scope(user),
            "must_change_password": bool(user.must_change_password)}


def update_profile(db: Session, user: User, body: ProfilePatch) -> User:
    sent = body.model_dump(exclude_unset=True, exclude_none=True)
    if "name" in sent:
        user.name = sent["name"].strip()
    if "preferred_language" in sent:
        user.preferred_language = sent["preferred_language"]
    if "accessibility" in sent:
        user.accessibility = {**(user.accessibility or {}), **{k: v for k, v in sent["accessibility"].items() if v is not None}}
    db.flush()
    return user
