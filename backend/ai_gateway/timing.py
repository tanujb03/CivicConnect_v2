"""Per-request AI timing: provider time (inside the HTTP calls) vs waited time (throttle, budget waits, retry sleeps) vs the gateway's total, plus the request-level cap.

A ``ContextVar`` accumulator. The gateway calls ``start()`` at the top of a public method; every provider call (``openai_compat._post``) calls ``add(...)``; the gateway reads
``snapshot()`` at the end and puts it into ``ai_metadata["timing"]``. Threads: the AI endpoints are plain ``def`` handlers, so FastAPI runs each in ONE worker thread with its
own copy of the context, and the gateway method plus every provider call it makes run on that thread (``ai.inference`` starts no threads). A caller that moved provider work to
another thread would have to copy the context (``contextvars.copy_context().run``); without a ``start()`` in the current context ``add`` is a no-op and ``snapshot`` is zeros.

Request deadline (``AI_REQUEST_DEADLINE_S``, default 30): the total time ONE request may spend in provider calls (primary, fallback, localisation, retries, waits). The time used is
the accumulated ``provider_ms + waited_ms`` of the finished calls (so it works with any clock). Before a call or a fallback starts, ``remaining()`` is checked: a call needs at least
``min_call_s`` (6 s, or a fifth of a short deadline) to be worth starting; each call's own deadline becomes min(AI_PROVIDER_TIMEOUT_S, remaining).
"""
from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any, Mapping, TypedDict

log = logging.getLogger("civicconnect.ai.timing")
DEFAULT_REQUEST_DEADLINE_S = 30.0
MIN_CALL_S = 6.0                 # a provider call needs at least this much of the request budget to be started (healthy calls take 1.5 to 5.4 s)


class Timing(TypedDict):
    provider_ms: int
    waited_ms: int
    provider_calls: int


def request_deadline_s(env: Mapping[str, str]) -> float:
    """``AI_REQUEST_DEADLINE_S`` in seconds: unset, empty or 0 mean the default (30); anything that is not a positive number is a configuration error."""
    raw = (env.get("AI_REQUEST_DEADLINE_S") or "").strip()
    if not raw:
        return DEFAULT_REQUEST_DEADLINE_S
    try:
        value = float(raw)
    except ValueError:
        raise ValueError("AI_REQUEST_DEADLINE_S must be a number of seconds (for example 30)") from None
    if value != value or value in (float("inf"), float("-inf")) or value < 0:
        raise ValueError("AI_REQUEST_DEADLINE_S must be a positive number of seconds (for example 30)")
    return value or DEFAULT_REQUEST_DEADLINE_S


_acc: ContextVar[dict[str, Any] | None] = ContextVar("civic_ai_timing", default=None)


def start(request_deadline: float | None = None) -> None:
    """Begin a fresh accumulator in the current context (a second ``start`` restarts it: the request deadline is per request). ``None`` = no request deadline."""
    _acc.set({"provider_ms": 0.0, "waited_ms": 0.0, "provider_calls": 0, "deadline_s": request_deadline, "reached": False})


def add(provider_ms: float, waited_ms: float, calls: int = 1) -> None:
    acc = _acc.get()
    if acc is not None:
        acc["provider_ms"] += provider_ms
        acc["waited_ms"] += waited_ms
        acc["provider_calls"] += calls


def deadline_s() -> float | None:
    acc = _acc.get()
    return acc["deadline_s"] if acc is not None else None


def remaining() -> float | None:
    """Seconds of the request budget left (may be negative); None when no request deadline is active."""
    acc = _acc.get()
    if acc is None or acc["deadline_s"] is None:
        return None
    return acc["deadline_s"] - (acc["provider_ms"] + acc["waited_ms"]) / 1000.0


def spent() -> bool:
    """True when too little of the request budget is left to start another provider call. Logs ``ai request deadline reached`` once per request."""
    left, acc = remaining(), _acc.get()
    if left is None or acc is None or left >= min(MIN_CALL_S, acc["deadline_s"] / 5.0):
        return False
    if not acc["reached"]:
        acc["reached"] = True
        log.warning("ai request deadline reached: %.0f s of %.0f s spent in %d provider call(s); further provider calls are skipped and the request degrades",
                    acc["deadline_s"] - left, acc["deadline_s"], acc["provider_calls"])
    return True


def snapshot() -> Timing:
    acc = _acc.get() or {}
    return {"provider_ms": int(acc.get("provider_ms", 0)), "waited_ms": int(acc.get("waited_ms", 0)), "provider_calls": int(acc.get("provider_calls", 0))}
