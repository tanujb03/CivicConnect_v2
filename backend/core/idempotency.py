"""Idempotency-Key handling (§51A.1, §51A.16)."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.exceptions import CivicConnectException
from backend.models import IdempotencyKey


def _hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def require_key(key: str | None) -> str:
    if not key or not key.strip():
        raise CivicConnectException("IDEMPOTENCY_KEY_REQUIRED", "This request needs an Idempotency-Key header (a client generated UUID).", 400)
    if len(key) > 128:
        raise CivicConnectException("VALIDATION_ERROR", "Idempotency-Key is too long.", 422, {"field": "Idempotency-Key"})
    return key.strip()


def run_idempotent(db: Session, *, user_id: str, key: str | None, method: str, path: str, payload: Any,
                   handler: Callable[[], tuple[int, Any, str | None]], required: bool = True) -> tuple[int, Any, bool]:
    """Runs ``handler`` once per (user, key). ``handler`` writes through ``db`` and returns ``(status, body, resource_id)``; everything (the writes and the stored
    response) commits atomically. A retry with the same key and body gets the SAME status and body (``replayed=True``); the same key with another body is refused.
    A handler that raises stores nothing, so the client may retry with the same key."""
    if not required and not (key and key.strip()):
        try:                                                 # no key sent and none required: just run it
            status, body, _ = handler()
            db.commit()
            return status, body, False
        except Exception:
            db.rollback()
            raise
    key = require_key(key)
    digest = _hash(payload)

    def existing() -> IdempotencyKey | None:
        return db.execute(select(IdempotencyKey).where(IdempotencyKey.user_id == user_id, IdempotencyKey.key == key)).scalar_one_or_none()

    def replay(row: IdempotencyKey) -> tuple[int, Any, bool]:
        if row.request_hash != digest or row.method != method or row.path != path:
            raise CivicConnectException("IDEMPOTENCY_KEY_REUSED", "This Idempotency-Key was already used for a different request.", 422)
        return row.status_code, row.response_json, True

    row = existing()
    if row is not None:
        return replay(row)
    try:
        status, body, resource_id = handler()
        db.add(IdempotencyKey(user_id=user_id, key=key, method=method, path=path, request_hash=digest, status_code=status,
                              response_json=json.loads(json.dumps(body, default=str)), resource_id=resource_id))
        db.commit()
        return status, body, False
    except IntegrityError:
        db.rollback()               # a concurrent request with the same key won the race
        row = existing()
        if row is None:
            raise
        return replay(row)
    except Exception:
        db.rollback()
        raise
