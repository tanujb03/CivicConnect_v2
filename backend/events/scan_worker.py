"""Background malware-scan worker (design §44): one daemon thread sweeping READY + PENDING evidence through clamd (``backend/services/malware_scan.py``).

Not a Redis consumer on purpose: the database is the queue, so a scan can never be lost when Redis is down or the process restarts.
Start it with ``start_scan_worker()`` (a no-op unless ``SCAN_ENABLED``); registration lives in ``backend/events/workers.py``.
"""
from __future__ import annotations

import logging
import threading

from backend.core.config import settings

log = logging.getLogger("civicconnect.scan_worker")

_thread: threading.Thread | None = None
_stop = threading.Event()
_start_lock = threading.Lock()


def run_once(session_factory=None, client=None) -> dict:
    """One sweep in its own session; never raises (a bad pass is logged and counted under ``failed``)."""
    from backend.services import malware_scan
    if session_factory is None:
        from backend.db import session as dbs
        session_factory = dbs.SessionLocal
    try:
        with session_factory() as db:
            try:
                out = malware_scan.scan_pending(db, client=client)
                db.commit()
                return {**out, "failed": 0}
            except Exception:
                db.rollback()
                raise
    except Exception as exc:
        log.warning("malware scan pass failed: %s", type(exc).__name__)
        return {"scanned": 0, "clean": 0, "infected": 0, "errors": 0, "retried": 0, "skipped": 0, "failed": 1}


def _loop(stop: threading.Event) -> None:
    log.info("Malware scan worker started (interval %.1f s)", settings.SCAN_WORKER_INTERVAL_S)
    while settings.SCAN_ENABLED and not stop.is_set():
        run_once()
        stop.wait(max(0.5, float(settings.SCAN_WORKER_INTERVAL_S)))


def start_scan_worker() -> threading.Thread | None:
    """Start the single scan thread (daemon). Returns None when scanning is disabled, or the running thread if it was already started."""
    global _thread
    if not settings.SCAN_ENABLED:
        log.info("Malware scan disabled (SCAN_ENABLED=false); worker not started.")
        return None
    with _start_lock:
        if _thread is not None and _thread.is_alive():
            return _thread
        _stop.clear()
        _thread = threading.Thread(target=_loop, args=(_stop,), daemon=True, name="worker-scan-1")
        _thread.start()
        return _thread


def stop_scan_worker(timeout: float = 5.0) -> None:
    """Tests / shutdown hook."""
    global _thread
    _stop.set()
    if _thread is not None:
        _thread.join(timeout)
        _thread = None
