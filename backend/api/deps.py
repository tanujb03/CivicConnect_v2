"""Shared route helpers."""
from __future__ import annotations

from typing import Any, Callable, Optional

from fastapi import Header, Response
from sqlalchemy.orm import Session

from backend.core.idempotency import run_idempotent

IdempotencyHeader = Header(None, alias="Idempotency-Key", description="Client generated UUID; a retry with the same key replays the first response (§51A.1).")


def idempotent(db: Session, response: Response, *, user_id: str, key: Optional[str], method: str, path: str, payload: Any,
               handler: Callable[[], tuple[int, Any, Optional[str]]], required: bool = True) -> Any:
    status, body, replayed = run_idempotent(db, user_id=user_id, key=key, method=method, path=path, payload=payload, handler=handler, required=required)
    response.status_code = status
    if replayed:
        response.headers["Idempotent-Replayed"] = "true"
    return body
