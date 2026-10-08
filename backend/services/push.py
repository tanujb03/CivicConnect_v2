"""Expo push (§53): the device registry of the apps and the delivery of ``Notification`` rows to Expo's free push service.

Flow: ``notifications.notify`` marks a new row ``PENDING`` when the user has an active device token and ``notification_policy.push`` is on (``mark_pending``); the push worker
(``backend/events/push_worker.py``) calls ``deliver_pending`` (send, ``PENDING`` -> ``SENT`` / ``FAILED`` / ``SKIPPED``) and ``check_receipts`` (second pass, revokes tokens Expo
reports as ``DeviceNotRegistered``). Nothing here runs inside a request and a failure never reaches the notification write.

Delivery guarantee: AT LEAST ONCE. All messages of one notification travel in one batch, the results of each batch are committed before the next request, and on PostgreSQL the
rows are selected ``FOR UPDATE SKIP LOCKED`` so two workers do not take the same rows. A crash between Expo's answer and the commit can still send one batch twice (and two
overlapping passes on SQLite, which has no row locks, could too: the app runs one worker). Failures that say nothing about a message (HTTP 429, 5xx, timeouts, transport errors,
an unreadable answer) never use up an attempt and never fail a row: the pass stops and the worker backs off. HTTP 401 / 403 (wrong ``EXPO_ACCESS_TOKEN``) is logged once and also
costs no attempt. An HTTP 400 is bisected down to the message(s) Expo rejects (this also copes with tokens of several Expo projects in one request); only those count an attempt.

What leaves the system, per message, to Expo and through it to Apple / Google (they can read it, and it shows on the lock screen): the notification title (cut to 100 chars), the
message (cut to 178 chars), ``case_id``, the notification ``type`` and the ``notification_id``, plus the device's push token. No coordinates, no case body, no names beyond what
the localised title / message already say. Neither the Expo access token nor a full push token is ever logged (at most ``TOKEN_LOG_CHARS`` characters of a token). Remote push
does not work in Expo Go; it needs a development build.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.exceptions import CivicConnectException
from backend.models import DeviceToken, Notification, SystemSetting, User
from backend.schemas.platform import DeviceTokenIn
from backend.services.audit import record_audit

log = logging.getLogger("civicconnect.push")

TOKEN_LOG_CHARS = 14
BODY_MAX = 178                                     # Expo shows about this much of a body on the lock screen
TITLE_MAX = 100
DEVICE_LIST_MAX = 50                               # GET /me/devices returns at most this many
RECEIPT_IDS_MAX = 300                              # Expo: at most 300 ids per getReceipts request
RECEIPT_MIN_AGE = timedelta(minutes=15)            # Expo: receipts are ready about 15 minutes after the send
RECEIPT_TTL = timedelta(hours=24)                  # Expo keeps receipts for 24 hours
RECEIPT_COLUMN = 128                               # Notification.push_receipt_id
NOT_REGISTERED = "DeviceNotRegistered"
FALLBACK_TITLE, FALLBACK_BODY = "CivicConnect", "You have a new update."


def mask(token: str | None) -> str:
    """The only form of a push token that may reach a log line."""
    return (token or "")[:TOKEN_LOG_CHARS] + "..."


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------------------------------------ device registry
def out(row: DeviceToken) -> dict[str, Any]:
    """``DeviceTokenOut`` as a dict; the token value is never returned."""
    return {"id": row.id, "platform": row.platform, "device_id": row.device_id, "locale": row.locale, "created_at": row.created_at, "last_seen_at": row.last_seen_at,
            "revoked_at": row.revoked_at}


def register_device(db: Session, user: User, body: DeviceTokenIn) -> tuple[DeviceToken, bool]:
    """Upsert by token: the same token is always the same row, bound to the caller (a token held by another user is rebound: the phone changed hands), ``revoked_at``
    cleared, ``last_seen_at`` refreshed. Returns ``(row, created)``. Audited only when something changes hands or state (not on every app start). Caller commits."""
    now = _now()
    row = db.execute(select(DeviceToken).where(DeviceToken.expo_push_token == body.expo_push_token)).scalar_one_or_none()
    created = row is None
    if created:
        row = DeviceToken(user_id=user.id, platform=body.platform, expo_push_token=body.expo_push_token, device_id=body.device_id, locale=body.locale, created_at=now, last_seen_at=now)
        try:
            with db.begin_nested():
                db.add(row)
        except IntegrityError:                               # a concurrent registration of the same token won the race: fall through to the update
            row = db.execute(select(DeviceToken).where(DeviceToken.expo_push_token == body.expo_push_token)).scalar_one()
            created = False
    if created:
        record_audit(db, actor_id=user.id, action="device.registered", entity_type="device_token", entity_id=row.id, after={"platform": row.platform})
        _enforce_limit(db, user, row, now)
        return row, True
    moved, revived = row.user_id != user.id, row.revoked_at is not None
    before = {"user_id": row.user_id, "revoked": revived}
    row.user_id, row.platform, row.last_seen_at, row.revoked_at = user.id, body.platform, now, None
    if moved:                                                # new owner: nothing of the old binding survives
        row.device_id, row.locale = body.device_id, body.locale
    else:
        row.device_id, row.locale = body.device_id or row.device_id, body.locale or row.locale
    db.flush()
    if moved or revived:
        record_audit(db, actor_id=user.id, action="device.rebound" if moved else "device.reactivated", entity_type="device_token", entity_id=row.id, before=before,
                     after={"user_id": user.id, "platform": row.platform})
        _enforce_limit(db, user, row, now)
    return row, False


def _enforce_limit(db: Session, user: User, keep: DeviceToken, now: datetime) -> None:
    """At most ``PUSH_MAX_DEVICES_PER_USER`` active tokens per user: the least recently seen other ones are revoked (audited with reason ``limit``)."""
    cap = max(1, settings.PUSH_MAX_DEVICES_PER_USER)
    others = list(db.execute(select(DeviceToken).where(DeviceToken.user_id == user.id, DeviceToken.revoked_at.is_(None), DeviceToken.id != keep.id)
                             .order_by(DeviceToken.last_seen_at, DeviceToken.id)).scalars())
    for old in others[:max(0, len(others) + 1 - cap)]:
        old.revoked_at = now
        record_audit(db, actor_id=user.id, action="device.revoked", entity_type="device_token", entity_id=old.id, before={"revoked": False}, after={"revoked": True, "reason": "limit"})
    db.flush()


def list_devices(db: Session, user: User, *, include_revoked: bool = False) -> list[DeviceToken]:
    q = select(DeviceToken).where(DeviceToken.user_id == user.id)
    if not include_revoked:
        q = q.where(DeviceToken.revoked_at.is_(None))
    return list(db.execute(q.order_by(DeviceToken.created_at.desc(), DeviceToken.id).limit(DEVICE_LIST_MAX)).scalars())


def revoke_device(db: Session, user: User, device_id: str) -> DeviceToken:
    """Revokes one of the caller's devices; another user's id answers 404. Repeating it changes nothing (the first ``revoked_at`` stays). Caller commits."""
    row = db.execute(select(DeviceToken).where(DeviceToken.id == device_id, DeviceToken.user_id == user.id)).scalar_one_or_none()
    if row is None:
        raise CivicConnectException("DEVICE_NOT_FOUND", "The device does not exist.", 404)
    if row.revoked_at is None:
        row.revoked_at = _now()
        db.flush()
        record_audit(db, actor_id=user.id, action="device.revoked", entity_type="device_token", entity_id=row.id, before={"revoked": False}, after={"revoked": True})
    return row


def revoke_device_by_token(db: Session, user_id: str, expo_push_token: str, reason: str = "logout") -> bool:
    """Revokes the live device row with this token IF it belongs to ``user_id`` (logout: the refresh token's owner). Unknown, other users' and already revoked tokens change
    nothing and say nothing (returns False). The audit row never holds the token. Caller commits."""
    row = db.execute(select(DeviceToken).where(DeviceToken.expo_push_token == expo_push_token, DeviceToken.user_id == user_id, DeviceToken.revoked_at.is_(None))).scalar_one_or_none()
    if row is None:
        return False
    row.revoked_at = _now()
    db.flush()
    record_audit(db, actor_id=user_id, action="device.revoked", entity_type="device_token", entity_id=row.id, before={"revoked": False}, after={"revoked": True, "reason": reason})
    return True


# ------------------------------------------------------------------------------------------------ marking (called by notify)
def push_enabled(db: Session) -> bool:
    """The effective ``notification_policy.push`` (the stored value, else the registry default)."""
    from backend.services.settings import REGISTRY
    row = db.get(SystemSetting, "notification_policy")
    value = row.value_json if row is not None else REGISTRY["notification_policy"].default()
    return bool(value.get("push", True)) if isinstance(value, dict) else True


def _active_tokens(db: Session, user_ids: Iterable[str]) -> dict[str, list[DeviceToken]]:
    """Active tokens of the ACTIVE users among ``user_ids``, most recently seen first."""
    ids = list(dict.fromkeys(user_ids))
    by_user: dict[str, list[DeviceToken]] = {}
    if ids:
        q = (select(DeviceToken).join(User, User.id == DeviceToken.user_id).where(DeviceToken.user_id.in_(ids), DeviceToken.revoked_at.is_(None), User.is_active.is_(True))
             .order_by(DeviceToken.last_seen_at.desc(), DeviceToken.id))
        for t in db.execute(q).scalars():
            by_user.setdefault(t.user_id, []).append(t)
    return by_user


def mark_pending(db: Session, notifications: list[Notification]) -> int:
    """``NONE`` -> ``PENDING`` for the rows whose user has an active token while the push policy is on. Never raises: any failure leaves the rows ``NONE``. Returns the count."""
    if not notifications:
        return 0
    try:
        with db.begin_nested():
            if not push_enabled(db):
                return 0
            with_tokens = set(_active_tokens(db, (n.user_id for n in notifications)))
            marked = [n for n in notifications if n.user_id in with_tokens]
            for n in marked:
                n.push_status = "PENDING"
            db.flush()
        return len(marked)
    except Exception as e:
        log.debug("push marking skipped: %s", type(e).__name__)
        for n in notifications:                              # the savepoint rolled the column back in the database; keep the objects honest too
            n.push_status = "NONE"
        return 0


# ------------------------------------------------------------------------------------------------ sending
def _headers() -> dict[str, str]:
    h = {"Accept": "application/json", "Accept-Encoding": "gzip, deflate", "Content-Type": "application/json"}
    if settings.EXPO_ACCESS_TOKEN:
        h["Authorization"] = f"Bearer {settings.EXPO_ACCESS_TOKEN}"
    return h


def _retry_after(r: httpx.Response) -> float | None:
    try:
        v = float(r.headers.get("Retry-After", ""))
        return v if 0 <= v <= 3600 else None
    except ValueError:
        return None


def _tag(token: str) -> str:
    """A 4-hex fingerprint of a token: lets a receipt be traced back to the device without storing the token (the column holds ``receipt~tag`` entries)."""
    return hashlib.sha256(token.encode()).hexdigest()[:4]


def _join(entries: list[str]) -> tuple[str | None, int]:
    """Fits whole ``receipt~tag`` entries into the 128-character column, dropping the OLDEST (first) ones when they do not all fit; returns ``(value, dropped)``."""
    kept = list(entries)
    while kept and len(",".join(kept)) > RECEIPT_COLUMN:
        kept.pop(0)
    return (",".join(kept) or None), len(entries) - len(kept)


def _split(value: str | None) -> list[tuple[str, str | None]]:
    out_ = []
    for part in (value or "").split(","):
        rid, _, tag = part.strip().partition("~")
        if rid:
            out_.append((rid, tag or None))
    return out_


@dataclass
class _Msg:
    n: Notification
    token: DeviceToken

    def payload(self) -> dict[str, Any]:
        p = self.n.payload if isinstance(self.n.payload, dict) else {}
        title = str(p.get("title") or FALLBACK_TITLE)
        body = str(p.get("message") or FALLBACK_BODY)
        if len(title) > TITLE_MAX:
            title = title[:TITLE_MAX - 3] + "..."
        if len(body) > BODY_MAX:
            body = body[:BODY_MAX - 3] + "..."
        return {"to": self.token.expo_push_token, "title": title, "body": body, "data": {"case_id": p.get("case_id"), "type": self.n.type, "notification_id": self.n.id},
                "sound": "default", "channelId": "default"}


@dataclass
class _Out:
    """What happened to one message: ``ok`` (receipt id kept), ``gone`` (DeviceNotRegistered), ``fail`` (Expo rejected it: costs an attempt) or ``pending`` (unknown: free retry)."""
    kind: str
    receipt: str | None = None


def _send(client: httpx.Client, batch: list[dict[str, Any]]) -> tuple[list | None, str | None, float | None, str]:
    """``(tickets, error, retry_after_s, kind)``; ``tickets`` is None when the whole request failed. ``kind``: ``ok``, ``transient`` (429 / 5xx / transport error / unreadable answer),
    ``config`` (401 / 403: bad credentials) or ``bad`` (any other refusal, e.g. 400: some message of the batch is invalid)."""
    try:
        r = client.post(settings.EXPO_PUSH_URL, json=batch, headers=_headers())
    except Exception as e:
        return None, type(e).__name__, None, "transient"
    if r.status_code in (401, 403):
        return None, f"HTTP {r.status_code}", None, "config"
    if r.status_code == 429 or r.status_code >= 500:
        return None, f"HTTP {r.status_code}", _retry_after(r), "transient"
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}", None, "bad"
    try:
        data = r.json()["data"]
    except Exception:
        return None, "unreadable response", None, "transient"
    if not isinstance(data, list) or len(data) != len(batch):
        return None, "unexpected response shape", None, "transient"
    return data, None, None, "ok"


def _ticket(m: _Msg, t: Any) -> _Out:
    status = t.get("status") if isinstance(t, dict) else None
    if status == "ok":
        return _Out("ok", f"{t['id']}~{_tag(m.token.expo_push_token)}" if t.get("id") else None)
    detail = (t.get("details") or {}).get("error") if isinstance(t, dict) and isinstance(t.get("details"), dict) else None
    if status == "error" and detail == NOT_REGISTERED:
        return _Out("gone")
    log.warning("push ticket error (%s) for token %s", detail or "unknown", mask(m.token.expo_push_token))
    return _Out("fail")


def _dispatch(http: httpx.Client, msgs: list[_Msg], stats: dict[str, Any]) -> tuple[list[_Out], str | None]:
    """Sends ``msgs`` and returns one ``_Out`` per message plus an abort reason (``transient`` / ``config`` / None). A refused request (``bad``) is bisected until the rejected
    message(s) are isolated, so one invalid message (or tokens of two Expo projects in one request) cannot hold the healthy ones back."""
    stats["requests"] += 1
    tickets, err, retry, kind = _send(http, [m.payload() for m in msgs])
    if tickets is not None:
        return [_ticket(m, t) for m, t in zip(msgs, tickets)], None
    if kind == "bad":
        if len(msgs) == 1:
            log.warning("push message rejected by Expo (%s) for token %s", err, mask(msgs[0].token.expo_push_token))
            return [_Out("fail")], None
        mid = len(msgs) // 2
        left, abort = _dispatch(http, msgs[:mid], stats)
        if abort:
            return left + [_Out("pending")] * (len(msgs) - mid), abort
        right, abort = _dispatch(http, msgs[mid:], stats)
        return left + right, abort
    if kind == "config":
        stats["config_error"] = True
        log.error("Expo refused the credentials (%s); check EXPO_ACCESS_TOKEN. Pushes stay PENDING.", err)
        return [_Out("pending")] * len(msgs), "config"
    stats["request_failures"] += 1
    stats["retry_after_s"] = max(stats["retry_after_s"], retry or 0.0)
    log.warning("push request failed (%s) for %d message(s), first token %s; nothing is charged", err, len(msgs), mask(msgs[0].token.expo_push_token))
    return [_Out("pending")] * len(msgs), "transient"


def pending_query(dialect: str, limit: int, exclude: set[str] | None = None):
    """The oldest PENDING rows; on PostgreSQL ``FOR UPDATE SKIP LOCKED`` so overlapping workers never take the same rows (SQLite has no row locks)."""
    q = select(Notification).where(Notification.push_status == "PENDING")
    if exclude:
        q = q.where(Notification.id.not_in(exclude))
    q = q.order_by(Notification.created_at, Notification.id).limit(limit)
    return q.with_for_update(skip_locked=True) if dialect == "postgresql" else q


def deliver_pending(db: Session, *, client: httpx.Client | None = None, now: datetime | None = None, limit: int = 500) -> dict[str, Any]:
    """One sending pass over the oldest ``PENDING`` notifications. Never sleeps and never raises; each batch is committed as soon as its results are applied.

    Per notification: ``SENT`` when every message got an ok ticket (a rejected message next to an ok one does not hold it back; ``DeviceNotRegistered`` tokens are revoked), ``SKIPPED``
    when nobody can receive it any more (no active token, inactive user, push switched off, every token ``DeviceNotRegistered``), ``FAILED`` after ``PUSH_MAX_ATTEMPTS`` rejections without
    a delivery, else ``PENDING`` (a rejection costs one attempt; an unknown outcome costs none).
    Returns counters (``sent``, ``failed``, ``skipped``, ``deferred`` = still PENDING, ``revoked``, ``requests``, ``request_failures`` = transient failures, ``config_error``,
    ``retry_after_s``, ``receipt_overflow``) for the worker's backoff."""
    stats: dict[str, Any] = {"selected": 0, "sent": 0, "failed": 0, "skipped": 0, "deferred": 0, "revoked": 0, "requests": 0, "request_failures": 0, "config_error": False,
                             "retry_after_s": 0.0, "receipt_overflow": 0}
    try:
        _deliver(db, client, now or _now(), limit, stats)
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        log.warning("push delivery pass failed: %s", type(e).__name__)
        stats["error"] = type(e).__name__
    if stats["receipt_overflow"]:
        log.warning("push: %d receipt id(s) did not fit the %d-character column and were dropped (oldest first); their tokens are not receipt-checked",
                    stats["receipt_overflow"], RECEIPT_COLUMN)
    return stats


def _deliver(db: Session, client: httpx.Client | None, now: datetime, limit: int, stats: dict[str, Any]) -> None:
    enabled = push_enabled(db)
    size = max(1, min(settings.PUSH_BATCH_SIZE, 100))
    cap = max(1, min(settings.PUSH_MAX_DEVICES_PER_USER, size))          # all messages of one notification share one batch
    dialect = db.get_bind().dialect.name
    seen: set[str] = set()
    http = client or httpx.Client(timeout=15)
    try:
        while len(seen) < limit:
            rows = list(db.execute(pending_query(dialect, min(size, limit - len(seen)), seen)).scalars())
            if not rows:
                break
            tokens = _active_tokens(db, (n.user_id for n in rows)) if enabled else {}
            group: list[Notification] = []
            msgs: list[_Msg] = []
            for n in rows:
                toks = tokens.get(n.user_id, [])[:cap]
                if toks and msgs and len(msgs) + len(toks) > size:
                    break
                seen.add(n.id)
                stats["selected"] += 1
                if not toks:
                    n.push_status = "SKIPPED"
                    stats["skipped"] += 1
                    continue
                group.append(n)
                msgs.extend(_Msg(n, t) for t in toks)
            outs, abort = _dispatch(http, msgs, stats) if msgs else ([], None)
            _apply(db, group, msgs, outs, now, stats)
            db.commit()
            if abort:                                                      # transient trouble or bad credentials: stop, the worker backs off
                break
    finally:
        if client is None:
            http.close()


def _apply(db: Session, group: list[Notification], msgs: list[_Msg], outs: list[_Out], now: datetime, stats: dict[str, Any]) -> None:
    per: dict[str, list[_Out]] = {n.id: [] for n in group}
    dead: dict[str, DeviceToken] = {}
    for m, o in zip(msgs, outs):
        per[m.n.id].append(o)
        if o.kind == "gone":
            dead[m.token.id] = m.token
    for tok_ in dead.values():
        tok_.revoked_at = now
    stats["revoked"] += len(dead)
    for n in group:
        res = per[n.id]
        ok, gone, fail, unknown = ([o for o in res if o.kind == k] for k in ("ok", "gone", "fail", "pending"))
        if unknown:                                                        # some outcome is not known: retry later at no cost
            stats["deferred"] += 1
            continue
        n.push_attempts = (n.push_attempts or 0) + 1
        if ok:
            value, dropped = _join([o.receipt for o in ok if o.receipt])
            n.push_status, n.pushed_at, n.push_receipt_id = "SENT", now, value
            stats["sent"] += 1
            stats["receipt_overflow"] += dropped
        elif not fail:                                                     # every token was DeviceNotRegistered: nobody left to notify
            n.push_status = "SKIPPED"
            stats["skipped"] += 1
        elif n.push_attempts >= settings.PUSH_MAX_ATTEMPTS:
            n.push_status = "FAILED"
            stats["failed"] += 1
        else:
            stats["deferred"] += 1
    db.flush()


# ------------------------------------------------------------------------------------------------ receipts
def check_receipts(db: Session, *, client: httpx.Client | None = None, now: datetime | None = None, min_age: timedelta = RECEIPT_MIN_AGE, limit: int = 500) -> dict[str, Any]:
    """Second pass: asks Expo for the receipts of ``SENT`` notifications at least ``min_age`` old (<= 300 ids per request) and revokes the token behind every
    ``DeviceNotRegistered``. A resolved receipt id is removed from ``push_receipt_id`` (the column is emptied when none is left); ids Expo has forgotten (older than 24 hours)
    are dropped too. Never raises; the caller commits."""
    stats: dict[str, Any] = {"checked": 0, "resolved": 0, "revoked": 0, "receipt_errors": 0, "expired": 0, "request_failures": 0}
    try:
        _receipts(db, client, now or _now(), min_age, limit, stats)
    except Exception as e:
        log.warning("push receipt pass failed: %s", type(e).__name__)
        stats["error"] = type(e).__name__
    return stats


def _receipts(db: Session, client: httpx.Client | None, now: datetime, min_age: timedelta, limit: int, stats: dict[str, Any]) -> None:
    q = select(Notification).where(Notification.push_status == "SENT", Notification.push_receipt_id.is_not(None), Notification.pushed_at <= now - min_age)
    rows = list(db.execute(q.order_by(Notification.pushed_at).limit(limit)).scalars())
    ids = list(dict.fromkeys(rid for n in rows for rid, _ in _split(n.push_receipt_id)))
    if not ids:
        return
    got: dict[str, Any] = {}
    unknown: set[str] = set()                                # ids of a chunk whose request failed: never treated as expired
    own = client is None
    http = client or httpx.Client(timeout=15)
    try:
        for i in range(0, len(ids), RECEIPT_IDS_MAX):
            chunk = ids[i:i + RECEIPT_IDS_MAX]
            stats["checked"] += len(chunk)
            try:
                r = http.post(settings.EXPO_RECEIPTS_URL, json={"ids": chunk}, headers=_headers())
                data = r.json()["data"] if r.status_code == 200 else None
            except Exception as e:
                log.warning("push receipt request failed: %s", type(e).__name__)
                data = None
            if not isinstance(data, dict):
                stats["request_failures"] += 1
                unknown.update(chunk)
                continue
            got.update(data)
    finally:
        if own:
            http.close()
    with db.begin_nested():
        by_user: dict[str, list[DeviceToken]] | None = None
        for n in rows:
            keep: list[str] = []
            for rid, tag in _split(n.push_receipt_id):
                rec = got.get(rid)
                if rec is None:
                    if rid not in unknown and n.pushed_at is not None and now - n.pushed_at > RECEIPT_TTL:
                        stats["expired"] += 1
                    else:
                        keep.append(f"{rid}~{tag}" if tag else rid)
                    continue
                stats["resolved"] += 1
                if isinstance(rec, dict) and rec.get("status") == "error":
                    if isinstance(rec.get("details"), dict) and rec["details"].get("error") == NOT_REGISTERED and tag:
                        by_user = by_user if by_user is not None else _active_tokens(db, (x.user_id for x in rows))
                        for t in by_user.get(n.user_id, []):
                            if t.revoked_at is None and _tag(t.expo_push_token) == tag:
                                t.revoked_at = now
                                stats["revoked"] += 1
                                log.info("push token %s revoked: DeviceNotRegistered receipt", mask(t.expo_push_token))
                    else:
                        stats["receipt_errors"] += 1
            n.push_receipt_id = _join(keep)[0]
        db.flush()
