"""System settings (A13) over the ``system_settings`` table: six typed, validated keys with code defaults, audited writes (design §46).

``ai_confidence_threshold`` and ``duplicate_threshold`` are applied by the AI gateway (``effective_thresholds``); the other keys are stored and returned.
A missing row means "the default"; the defaults come from the same files the AI package reads (``ai_policy.v1.json`` / ``fusion_policy.v1.json`` / the taxonomy).
"""
from __future__ import annotations

import logging
import math
import re
import time
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.inference.config import AIPolicy, load_fusion_policy
from backend.core.exceptions import CivicConnectException
from backend.db import session as db_session
from backend.models import SystemSetting, User
from backend.services.audit import record_audit
from backend.services.taxonomy import taxonomy

log = logging.getLogger("civicconnect.settings")

PRIORITIES = ("LOW", "NORMAL", "HIGH", "URGENT", "CRITICAL")           # longest SLA first
LANGUAGE = re.compile(r"^[a-z]{2,3}(-[A-Za-z]{2,8})?$")
NOTIFICATION_KEYS = ("email", "sms", "push", "escalation_emails")
CACHE_SECONDS = 5.0


class SettingError(ValueError):
    pass


def _number(v: Any, lo: float, hi: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise SettingError("must be a number")
    if not lo <= v <= hi:
        raise SettingError(f"must be between {lo} and {hi}")
    return float(v)


def _integer(v: Any, lo: int, hi: int) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        if isinstance(v, float) and math.isfinite(v) and v == int(v):
            v = int(v)
        else:
            raise SettingError("must be a whole number")
    if not lo <= v <= hi:
        raise SettingError(f"must be between {lo} and {hi}")
    return int(v)


def _sla_hours(v: Any) -> dict[str, int]:
    if not isinstance(v, dict):
        raise SettingError(f"must be an object with the keys {', '.join(PRIORITIES)}")
    if set(v) != set(PRIORITIES):
        raise SettingError(f"must have exactly the keys {', '.join(PRIORITIES)}")
    out = {p: _integer(v[p], 1, 8760) for p in PRIORITIES}
    for longer, shorter in zip(PRIORITIES, PRIORITIES[1:]):
        if out[shorter] > out[longer]:
            raise SettingError(f"{shorter} ({out[shorter]} h) must not be longer than {longer} ({out[longer]} h)")
    return out


def _languages(v: Any) -> list[str]:
    if not isinstance(v, list) or not 1 <= len(v) <= 20:
        raise SettingError("must be a list of 1 to 20 language codes")
    if any(not isinstance(x, str) or not LANGUAGE.match(x) for x in v):
        raise SettingError("every entry must be a language code such as en, hi, mr or hi-Latn")
    if len(set(v)) != len(v):
        raise SettingError("language codes must be unique")
    if "en" not in v:
        raise SettingError("must contain en")
    return list(v)


def _notification_policy(v: Any) -> dict[str, bool]:
    if not isinstance(v, dict) or set(v) != set(NOTIFICATION_KEYS):
        raise SettingError(f"must be an object with exactly the keys {', '.join(NOTIFICATION_KEYS)}")
    if any(not isinstance(v[k], bool) for k in NOTIFICATION_KEYS):
        raise SettingError("every value must be true or false")
    return {k: v[k] for k in NOTIFICATION_KEYS}


@dataclass(frozen=True)
class SettingDef:
    key: str
    description: str
    default: Callable[[], Any]
    validate: Callable[[Any], Any]


def _default_sla_hours() -> dict[str, int]:
    t = taxonomy()
    return {**{p: t.sla_hours[t.priority_sla_class[p]] for p in PRIORITIES if p in t.priority_sla_class}, "CRITICAL": t.sla_hours.get("EMERGENCY", 4)}


REGISTRY: dict[str, SettingDef] = {d.key: d for d in (
    SettingDef("ai_confidence_threshold", "Below this confidence an AI intake proposal is flagged low-confidence and the local image model may propose instead (0 to 1).",
               lambda: float(AIPolicy.load().intake["low_confidence_threshold"]), lambda v: _number(v, 0.0, 1.0)),
    SettingDef("duplicate_threshold", "Similarity at or above which an AI fusion match is a POSSIBLE_DUPLICATE (0.5 to 1); below it, down to 0.5, it is only RELATED.",
               lambda: float(load_fusion_policy()["thresholds"]["possible_duplicate"]), lambda v: _number(v, 0.5, 1.0)),
    SettingDef("sla_hours_by_priority", "SLA hours per priority (LOW, NORMAL, HIGH, URGENT, CRITICAL); a higher priority never has a longer SLA.",
               _default_sla_hours, _sla_hours),
    SettingDef("supported_languages", "Language codes the apps offer; must contain en.", lambda: list(taxonomy().raw["supported_languages"]), _languages),
    SettingDef("notification_policy", "Which notification channels are on: email, sms, push, escalation_emails (no free email/SMS provider is wired yet, so only push is on).",
               lambda: {"email": False, "sms": False, "push": True, "escalation_emails": False}, _notification_policy),
    SettingDef("flag_review_threshold", "Number of open citizen flags on a case that triggers a staff review (1 to 100).", lambda: 3, lambda v: _integer(v, 1, 100)),
)}


def _rows(db: Session) -> dict[str, SystemSetting]:
    return {r.key: r for r in db.execute(select(SystemSetting).where(SystemSetting.key.in_(list(REGISTRY)))).scalars()}


def _current(rows: dict[str, SystemSetting], key: str) -> Any:
    row = rows.get(key)
    return REGISTRY[key].default() if row is None else row.value_json


def list_settings(db: Session) -> list[dict[str, Any]]:
    rows = _rows(db)
    out = []
    for key, d in REGISTRY.items():
        default, row = d.default(), rows.get(key)
        value = default if row is None else row.value_json
        out.append({"key": key, "value": value, "default": default, "is_default": value == default, "description": d.description,
                    "updated_by": row.updated_by if row else None, "updated_at": row.updated_at if row else None})
    return out


def update_settings(db: Session, actor: User, values: dict[str, Any], reason: str | None) -> list[str]:
    """All-or-nothing: every value is validated first (422 lists each bad key); only keys whose value changes are written and audited. Returns the changed keys.
    The caller commits."""
    errors, clean = [], {}
    for key, raw in values.items():
        if key not in REGISTRY:
            errors.append({"key": key, "message": f"unknown setting; known keys: {', '.join(REGISTRY)}"})
            continue
        try:
            clean[key] = REGISTRY[key].validate(raw)
        except SettingError as e:
            errors.append({"key": key, "message": str(e)})
    if errors:
        raise CivicConnectException("VALIDATION_ERROR", "One or more settings are invalid; nothing was changed.", 422, {"errors": errors})
    rows, changed = _rows(db), []
    for key, new in clean.items():
        old = _current(rows, key)
        if old == new:
            continue
        row = rows.get(key)
        if row is None:
            db.add(SystemSetting(key=key, value_json=new, updated_by=actor.id))
        else:
            row.value_json, row.updated_by = new, actor.id
        record_audit(db, actor_id=actor.id, action="settings.updated", entity_type="system_settings", entity_id=key, before={"value": old}, after={"value": new, "reason": reason})
        changed.append(key)
    db.flush()
    invalidate_cache()
    return changed


# ------------------------------------------------------------------------------------------------ what the AI gateway reads
_cache: dict[str, Any] = {"url": None, "at": 0.0, "value": None}


def invalidate_cache() -> None:
    _cache.update(url=None, at=0.0, value=None)


def effective_thresholds() -> dict[str, float]:
    """``{"ai_confidence_threshold", "duplicate_threshold"}`` for the AI gateway; cached for CACHE_SECONDS per database (a change reaches other processes within that time)
    and falling back to the defaults when the database cannot be read (the AI must keep answering)."""
    url, now = str(db_session.engine.url), time.monotonic()
    if _cache["url"] == url and now - _cache["at"] < CACHE_SECONDS:
        return dict(_cache["value"])
    try:
        with db_session.session_scope() as db:
            rows = _rows(db)
            value = {k: float(_current(rows, k)) for k in ("ai_confidence_threshold", "duplicate_threshold")}
    except Exception as e:
        log.warning("settings unreadable (%s); using the defaults", type(e).__name__)
        value = {k: float(REGISTRY[k].default()) for k in ("ai_confidence_threshold", "duplicate_threshold")}
    _cache.update(url=url, at=now, value=value)
    return dict(value)
