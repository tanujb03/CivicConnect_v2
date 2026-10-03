"""In-app notifications (§53): domain event -> Notification row (+ Redis stream message when Redis is up)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.exceptions import CivicConnectException
from backend.models import Notification, User
from backend.services import i18n

log = logging.getLogger("civicconnect.notifications")

TYPES = {"CASE_ASSIGNED", "CASE_UPDATED", "VERIFICATION_REQUESTED", "CASE_RESOLVED", "INCIDENT_CREATED", "WORK_ORDER_ASSIGNED"}


def notify(db: Session, user_ids: Iterable[str | None], type_: str, payload: dict[str, Any], *, template: str | None = None, params: dict[str, Any] | None = None) -> list[Notification]:
    """One Notification per distinct user. With ``template`` (a key of ``i18n.TEMPLATES``) the title and message are rendered from the fixed en / hi / mr templates in EACH
    recipient's ``preferred_language`` (no model involved) and the payload gains ``template``, ``params`` and ``language``; ``payload["title"]`` / ``["message"]`` stay the fields
    clients read and are the fallback text when the key is unknown."""
    assert type_ in TYPES, type_
    ids = list(dict.fromkeys(u for u in user_ids if u))
    langs = dict(db.execute(select(User.id, User.preferred_language).where(User.id.in_(ids))).all()) if (template and ids) else {}
    out, texts = [], []
    for uid in ids:
        data = payload
        if template:
            shown = i18n.render(template, langs.get(uid), params if params is not None else payload)
            if shown is not None:
                data = {**payload, "title": shown[0], "message": shown[1], "template": template, "language": shown[2], "params": {k: str(v) for k, v in (params or {}).items()}}
        n = Notification(user_id=uid, type=type_, payload=data)
        db.add(n)
        out.append(n)
        texts.append(data)
    db.flush()
    for n, data in zip(out, texts):
        try:
            from backend.events import emit_notification
            emit_notification(n.user_id, data.get("title", type_), data.get("message", ""), "case" if data.get("case_id") else "", data.get("case_id") or "")
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
