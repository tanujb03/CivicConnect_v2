"""Password hashing, access/refresh tokens and the authentication dependencies.

* Access tokens are short-lived signed JWTs (``sub``, ``role``, ``typ=access``). Refresh tokens are opaque random strings, stored only as a hash and rotated on use.
* Authorization never trusts a role sent by the client (design §43): routes that touch data use ``current_user`` (the User row, role read from the database).
  ``get_current_user`` / ``require_roles`` (token claims only) remain for endpoints that need no data access.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

import bcrypt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.exceptions import CivicConnectException
from backend.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token", auto_error=False)


# ------------------------------------------------------------------------------------------------ passwords
def _prehash(password: str) -> bytes:
    """bcrypt only reads the first 72 bytes (and bcrypt>=5 refuses longer input): hash first so every character counts."""
    return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt()).decode("ascii")


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(_prehash(plain_password), hashed_password.encode("ascii"))
    except ValueError:
        return False


# ------------------------------------------------------------------------------------------------ tokens
def create_access_token(subject: Union[str, Any], role: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    return jwt.encode({"exp": expire, "sub": str(subject), "role": role, "typ": "access"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def new_refresh_token() -> tuple[str, str]:
    """(token handed to the client, sha256 stored in the database)."""
    token = secrets.token_urlsafe(48)
    return token, hash_refresh_token(token)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _unauthorized(code: str, message: str) -> CivicConnectException:
    return CivicConnectException(code, message, 401)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise _unauthorized("AUTH_INVALID_TOKEN", "Could not validate credentials.")
    if payload.get("sub") is None or payload.get("typ", "access") != "access":
        raise _unauthorized("AUTH_INVALID_TOKEN", "Could not validate credentials.")
    return {"sub": payload["sub"], "role": payload.get("role")}


def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
    """Token claims only ({sub, role}); use ``current_user`` when the database state matters."""
    if not token:
        raise _unauthorized("AUTH_REQUIRED", "Authentication is required.")
    return decode_token(token)


def require_roles(*roles: str):
    """Role gate on token claims. Prefer ``require_staff`` / ``require_role_in`` from ``backend.core.permissions`` on data endpoints."""
    def _check(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in roles:
            raise CivicConnectException("AUTH_FORBIDDEN", "Insufficient permissions.", 403)
        return current_user
    return _check


def current_user(claims: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """The authenticated User row. The role comes from the database, so a demoted or deactivated account loses access immediately."""
    from backend.models import User
    user = db.get(User, claims["sub"])
    if user is None or not user.is_active:
        raise _unauthorized("AUTH_INVALID_TOKEN", "The account no longer exists or is inactive.")
    return user
