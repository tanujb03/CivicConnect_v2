"""In-app notifications (§53): domain event -> Notification row (+ Redis stream message when Redis is up)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.exceptions import CivicConnectException
from backend.models import Notification

log = logging.getLogger("civicconnect.notifications")

TYPES = {"CASE_ASSIGNED", "CASE_UPDATED", "VERIFICATION_REQUESTED", "CASE_RESOLVED", "INCIDENT_CREATED", "WORK_ORDER_ASSIGNED"}


def notify(db: Session, user_ids: Iterable[str | None], type_: str, payload: dict[str, Any]) -> list[Notification]:
    assert type_ in TYPES, type_
    out = []
    for uid in dict.fromkeys(u for u in user_ids if u):
        n = Notification(user_id=uid, type=type_, payload=payload)
        db.add(n)
        out.append(n)
    db.flush()
    for n in out:
        try:
            from backend.events import emit_notification
            emit_notification(n.user_id, payload.get("title", type_), payload.get("message", ""), "case" if payload.get("case_id") else "", payload.get("case_id") or "")
        except Exception as e:
            log.debug("notification propagation skipped: %s", type(e).__name__)
    return out


def serialize(n: Notification) -> dict:
    return {"id": n.id, "type": n.type, "payload": n.payload, "read_at": n.read_at, "created_at": n.created_at}


def mark_read(db: Session, user_id: str, notification_id: str) -> Notification:
    n = db.execute(select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)).scalar_one_or_none()
    if n is None:
        raise CivicConnectException("NOTIFICATION_NOT_FOUND", "The notification does not exist.", 404)
    if n.read_at is None:                               # idempotent: a second call keeps the first timestamp
        n.read_at = datetime.now(timezone.utc)
        db.flush()
    return n
