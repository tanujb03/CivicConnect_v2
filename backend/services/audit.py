"""AuditEvent writer (design §46). Append-only: this module only inserts."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from backend.models import AuditEvent

log = logging.getLogger("civicconnect.audit")


def record_audit(db: Session, *, actor_id: str | None, action: str, entity_type: str, entity_id: str | None, before: Any = None, after: Any = None) -> AuditEvent:
    ev = AuditEvent(actor_id=actor_id, action=action, entity_type=entity_type, entity_id=entity_id, before_json=before, after_json=after)
    db.add(ev)
    db.flush()
    try:                                              # propagation to the event stream is best effort and never breaks the request
        from backend.events import emit_audit
        emit_audit(actor_id, action, entity_id, {"entity_type": entity_type, "audit_id": ev.id})
    except Exception as e:
        log.debug("audit propagation skipped: %s", type(e).__name__)
    return ev
