"""Offline synchronisation (§51A.16, design §16/§19): an ordered batch of client-queued mutations, each applied at most once."""
from __future__ import annotations

import base64
import json
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.exceptions import CivicConnectException
from backend.core.idempotency import run_idempotent
from backend.core.permissions import CAPABILITIES, STAFF_ROLES
from backend.models import CaseEvent, CivicCase, User
from backend.schemas.case import CaseCreate, CasePatch, VerificationIn
from backend.schemas.sync import SyncMutationIn
from backend.services import cases as case_service
from backend.services import evidence as evidence_service
from backend.services import verification as verification_service
from backend.services.cases import visibility_clause


def encode_cursor(seq: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"seq": seq}).encode()).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return max(0, int(json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))["seq"]))
    except Exception:
        raise CivicConnectException("INVALID_CURSOR", "The sync cursor is not valid.", 422)


def _need(user: User, capability: str) -> None:
    if user.role not in CAPABILITIES[capability]:
        raise CivicConnectException("AUTH_FORBIDDEN", "Your role may not do this.", 403, {"capability": capability})


def _apply(db: Session, user: User, m: SyncMutationIn) -> tuple[int, Any, str | None]:
    """One mutation, through the same domain services as the REST endpoints."""
    p = dict(m.payload)
    if m.operation == "CREATE_CASE":
        _need(user, "create_case")
        p.setdefault("client_case_id", m.idempotency_key)
        case, _ = case_service.create_case(db, user, CaseCreate(**p))
        return 200, {"case_id": case.id, "case_number": case.case_number}, case.id
    case = case_service.get_visible_case(db, user, str(p.get("case_id", "")))
    if m.operation == "SUPPORT_CASE":
        _need(user, "create_case")
        case_service.add_support(db, user, case)
        return 200, {"case_id": case.id}, case.id
    if m.operation == "UNSUPPORT_CASE":
        case_service.remove_support(db, user, case)
        return 200, {"case_id": case.id}, case.id
    if m.operation == "ADD_EVIDENCE":
        evs = evidence_service.attach(db, user, list(p.get("evidence_ids", [])), case)
        return 200, {"case_id": case.id, "attached": len(evs)}, case.id
    if m.operation == "SUBMIT_VERIFICATION":
        _need(user, "verify_resolution")
        v, _ = verification_service.record(db, user, case, VerificationIn(**{k: p.get(k) for k in ("result", "comment", "evidence_ids") if k in p}))
        return 200, {"case_id": case.id, "verification_id": v.id}, v.id
    if m.operation == "PATCH_CASE":
        case_service.patch_case(db, user, case, CasePatch(**{k: v for k, v in p.items() if k != "case_id"}))
        return 200, {"case_id": case.id}, case.id
    raise CivicConnectException("VALIDATION_ERROR", "Unknown operation.", 422, {"operation": m.operation})


def _error(e: Exception) -> dict:
    if isinstance(e, CivicConnectException):
        return {"code": e.code, "message": e.message, "details": e.details}
    if isinstance(e, ValidationError):
        return {"code": "VALIDATION_ERROR", "message": "The mutation payload is invalid.", "details": {"errors": [{"loc": list(x["loc"]), "message": x["msg"]} for x in e.errors()]}}
    raise e


def process(db: Session, user: User, mutations: list[SyncMutationIn]) -> list[dict]:
    """Ordered; each mutation is its own transaction. APPLIED the first time, ALREADY_APPLIED when the key was seen (nothing is repeated), REJECTED with a stable error.
    Rejections are remembered too, so a retry returns the same verdict instead of re-running a failed operation."""
    results = []
    for m in mutations:
        def handler(m=m):
            savepoint = db.begin_nested()
            try:
                status, body, rid = _apply(db, user, m)
                savepoint.commit()
                return status, {"ok": True, **body}, rid
            except (CivicConnectException, ValidationError) as e:
                savepoint.rollback()
                return 422, {"ok": False, "error": _error(e)}, None
        try:
            _, body, replayed = run_idempotent(db, user_id=user.id, key=m.idempotency_key, method="POST", path="/sync/mutations",
                                               payload={"operation": m.operation, "payload": m.payload}, handler=handler)
        except CivicConnectException as e:           # same key, different content
            results.append({"idempotency_key": m.idempotency_key, "status": "REJECTED", "server_resource_id": None, "error": _error(e)})
            continue
        if body.get("ok"):
            results.append({"idempotency_key": m.idempotency_key, "status": "ALREADY_APPLIED" if replayed else "APPLIED",
                            "server_resource_id": body.get("case_id") or body.get("verification_id"), "error": None})
        else:
            results.append({"idempotency_key": m.idempotency_key, "status": "REJECTED", "server_resource_id": None, "error": body["error"]})
    return results


def max_visible_seq(db: Session, user: User) -> int:
    q = select(func.max(CaseEvent.seq))
    if user.role == "overlooker":
        return 0
    clause = visibility_clause(user)
    if clause is not True:
        q = q.where(CaseEvent.case_id.in_(select(CivicCase.id).where(clause)))
    if user.role not in STAFF_ROLES:
        q = q.where(CaseEvent.visibility == "PUBLIC")
    return db.execute(q).scalar() or 0


def changes_since(db: Session, user: User, cursor: str | None, limit: int = 100) -> dict:
    after = decode_cursor(cursor)
    clause = visibility_clause(user)
    q = db.query(CaseEvent).filter(CaseEvent.seq > after)
    if clause is not True:
        q = q.filter(CaseEvent.case_id.in_(select(CivicCase.id).where(clause)))
    if user.role not in STAFF_ROLES:
        q = q.filter(CaseEvent.visibility == "PUBLIC")
    rows = q.order_by(CaseEvent.seq).limit(limit + 1).all()
    more = len(rows) > limit
    rows = rows[:limit]
    ids = list(dict.fromkeys(e.case_id for e in rows))
    cases = {c.id: case_service.serialize_case(c) for c in db.execute(select(CivicCase).where(CivicCase.id.in_(ids))).scalars()} if ids else {}
    last = rows[-1].seq if rows else after
    return {"changes": [{"cursor": encode_cursor(e.seq), "case_id": e.case_id, "event_type": e.event_type, "timestamp": e.created_at} for e in rows], "cases": cases,
            "server_cursor": encode_cursor(last), "has_more": more}
