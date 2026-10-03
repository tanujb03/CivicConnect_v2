"""Accounts, sessions and profile (§51A.2, §51A.3)."""
from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.exceptions import CivicConnectException
from backend.core.permissions import CAPABILITIES, CITY_WIDE_ROLES
from backend.core.security import create_access_token, get_password_hash, hash_refresh_token, new_refresh_token, verify_password
from backend.models import RefreshToken, User
from backend.schemas.auth import ProfilePatch, RegisterIn

_DUMMY_HASH = get_password_hash("not-a-real-password")      # verified against when the account does not exist (no user-enumeration by timing)
MAX_FAILURES, LOCK_SECONDS = 5, 60
_failures: dict[str, list[float]] = defaultdict(list)       # per-process brute-force guard; put a shared limiter (Redis) in front for multi-worker deployments


def _normalize_identifier(identifier: str) -> tuple[str | None, str | None]:
    ident = identifier.strip()
    if "@" in ident:
        return ident.lower(), None
    return None, "".join(ch for ch in ident if ch.isdigit() or ch == "+")


def _throttle_check(key: str, now: float) -> None:
    recent = [t for t in _failures[key] if now - t < LOCK_SECONDS]
    _failures[key] = recent
    if len(recent) >= MAX_FAILURES:
        raise CivicConnectException("RATE_LIMITED", "Too many failed sign-in attempts. Try again in a minute.", 429, {"retry_after_seconds": int(LOCK_SECONDS - (now - recent[0]))})


def reset_throttle() -> None:
    _failures.clear()


def session_for(db: Session, user: User) -> dict:
    refresh, digest = new_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=digest, expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)))
    db.flush()
    return {"user": brief(user), "access_token": create_access_token(user.id, user.role), "refresh_token": refresh, "token_type": "bearer"}


def brief(user: User) -> dict:
    return {"id": user.id, "name": user.name, "role": user.role.upper()}


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
        _failures[key].append(now)
        raise CivicConnectException("AUTH_INVALID_CREDENTIALS", "Incorrect identifier or password.", 401)
    _failures.pop(key, None)
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


def access_scope(user: User) -> dict:
    return {"role": user.role.upper(), "city_wide": user.role in CITY_WIDE_ROLES, "department_id": user.department_id, "ward_id": user.ward_id,
            "capabilities": sorted(name for name, roles in CAPABILITIES.items() if user.role in roles)}


def profile(user: User) -> dict:
    return {"id": user.id, "name": user.name, "role": user.role.upper(), "email": user.email, "phone": user.phone, "preferred_language": user.preferred_language,
            "accessibility": user.accessibility or {}, "department_id": user.department_id, "ward_id": user.ward_id, "access_scope": access_scope(user)}


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
