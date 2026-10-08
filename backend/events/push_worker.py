"""Background loop of the Expo push sender (§53): one thread, one ``deliver_pending`` + ``check_receipts`` pass every ``PUSH_WORKER_INTERVAL_S`` seconds.

Failures never stop the loop and are logged without secrets. When Expo refuses a whole request (HTTP 429 / 5xx / timeout / transport error) the next pass waits 1 s, 2 s, 4 s, ...
(at most ``MAX_BACKOFF_S`` = 5 minutes), or the ``Retry-After`` Expo sent when that is longer; rejected credentials (HTTP 401 / 403) wait the full 5 minutes. Receipts are asked for
at most once per ``RECEIPT_EVERY_S`` (5 minutes) per process. Registered by ``backend/events/workers.py::start_background_workers``.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

import httpx

from backend.core.config import settings

log = logging.getLogger("civicconnect.push_worker")

MAX_BACKOFF_S = 300.0
RECEIPT_EVERY_S = 300.0                              # the receipt pass runs at most this often (Expo prepares receipts for ~15 minutes after a send)
_thread: threading.Thread | None = None
_last_receipts: float | None = None


def run_once(session_factory: Callable[[], Any] | None = None, client: httpx.Client | None = None) -> dict[str, Any]:
    """One pass in its own session: deliver pending notifications, then check receipts, commit. Swallows and logs every exception; the result carries ``error`` then."""
    from backend.db import session as dbs
    from backend.services import push
    global _last_receipts
    result: dict[str, Any] = {}
    try:
        with (session_factory or dbs.SessionLocal)() as db:
            try:
                result["deliver"] = push.deliver_pending(db, client=client)
                if _last_receipts is None or time.monotonic() - _last_receipts >= RECEIPT_EVERY_S:
                    _last_receipts = time.monotonic()
                    result["receipts"] = push.check_receipts(db, client=client)
                else:
                    result["receipts"] = {"skipped": True}
                db.commit()
            except Exception:
                db.rollback()
                raise
    except Exception as e:
        log.warning("push worker pass failed: %s", type(e).__name__)
        result["error"] = type(e).__name__
    return result


def next_delay(result: dict[str, Any], failures: int) -> tuple[float, int]:
    """``(seconds to wait, consecutive failing passes)``: the normal interval after a clean pass, else exponential backoff (honouring Expo's Retry-After)."""
    deliver = result.get("deliver") or {}
    if deliver.get("config_error"):
        return MAX_BACKOFF_S, failures + 1
    bad = bool(result.get("error") or deliver.get("error") or deliver.get("request_failures"))
    if not bad:
        return settings.PUSH_WORKER_INTERVAL_S, 0
    failures += 1
    return max(settings.PUSH_WORKER_INTERVAL_S, min(MAX_BACKOFF_S, 2.0 ** min(failures - 1, 20)), float(deliver.get("retry_after_s") or 0.0)), failures


def _loop(stop: threading.Event | None = None) -> None:
    failures = 0
    log.info("Push worker starting (interval %.1fs).", settings.PUSH_WORKER_INTERVAL_S)
    while stop is None or not stop.is_set():
        delay, failures = next_delay(run_once(), failures)
        if stop is not None:
            stop.wait(delay)
        else:
            threading.Event().wait(delay)


def start_push_worker(stop: threading.Event | None = None) -> threading.Thread:
    """Starts the daemon thread once per process (a second call returns the running thread)."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return _thread
    _thread = threading.Thread(target=_loop, args=(stop,), daemon=True, name="worker-push-1")
    _thread.start()
    return _thread
