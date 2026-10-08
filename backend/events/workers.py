"""
Background worker loops that consume Redis Streams.

Each worker runs in its own thread, started by the FastAPI lifespan handler.
Workers are fault-tolerant: they catch all exceptions, log them, and keep running.

Usage (in main.py lifespan):
    from backend.events.workers import start_background_workers
    start_background_workers()
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Callable

import redis as redis_lib

from backend.core.telemetry import consumer_span
from backend.events.publisher import (
    GROUP_AI_WORKERS,
    GROUP_AUDIT_WRITERS,
    GROUP_NOTIFICATIONS,
    GROUP_SYNC_WORKERS,
    HEALTH_CHECK_INTERVAL_S,
    STREAM_AI_JOBS,
    STREAM_AUDIT,
    STREAM_NOTIFICATIONS,
    STREAM_SYNC,
    make_client,
)

log = logging.getLogger("civicconnect.workers")

WORKER_BLOCK_MS = 5_000   # block 5 s waiting for new messages
# The client's socket timeouts MUST exceed the blocking read, otherwise redis-py (>= 8 defaults both to 5 s) aborts every idle poll with "Timeout reading
# from socket". Workers run in background threads, so unlike the request path (publisher.get_redis, 2 s connect) they can afford to wait.
WORKER_SOCKET_TIMEOUT_S = WORKER_BLOCK_MS / 1000 + 10
WORKER_CONNECT_TIMEOUT_S = WORKER_SOCKET_TIMEOUT_S
WORKER_COUNT_PER_STREAM = 1

_threads: list[threading.Thread] = []
_worker_client: redis_lib.Redis | None = None
_worker_client_lock = threading.Lock()


def get_worker_redis() -> redis_lib.Redis | None:
    """The shared client of the blocking stream readers (its own pool, so a 5 s read never occupies a publisher's connection); None if Redis is unreachable."""
    global _worker_client
    with _worker_client_lock:
        if _worker_client is None:
            try:
                client = make_client(connect_timeout=WORKER_CONNECT_TIMEOUT_S, socket_timeout=WORKER_SOCKET_TIMEOUT_S, health_check_interval=HEALTH_CHECK_INTERVAL_S)
                client.ping()
                _worker_client = client
            except Exception as exc:
                log.warning("Worker Redis client unavailable (%s); retrying in 10 s.", exc)
                return None
        return _worker_client


def _pause(seconds: float, stop: threading.Event | None) -> None:
    (stop.wait(seconds) if stop is not None else time.sleep(seconds))


# ── Generic stream reader ─────────────────────────────────────────────────────

def _stream_worker(
    stream: str,
    group: str,
    consumer_name: str,
    handler: Callable[[dict], None],
    stop: threading.Event | None = None,
) -> None:
    """Read messages from a Redis Stream consumer group and call *handler*. ``stop`` ends the loop (tests); production threads are daemons and never stop."""
    log.info("Worker starting: stream=%s consumer=%s", stream, consumer_name)
    while stop is None or not stop.is_set():
        r = get_worker_redis()
        if r is None:
            _pause(10, stop)
            continue
        try:
            results = r.xreadgroup(
                group, consumer_name, {stream: ">"}, count=10, block=WORKER_BLOCK_MS
            )
            if not results:
                continue
            for _stream, messages in results:
                for entry_id, fields in messages:
                    try:
                        # Deserialise JSON-encoded values
                        decoded = {
                            k: (json.loads(v) if v.startswith("{") or v.startswith("[") else v)
                            for k, v in fields.items()
                        }
                        with consumer_span(stream, entry_id, fields):      # WP8: continues the producer's trace (no-op while OTEL_ENABLED is false)
                            handler(decoded)
                        r.xack(stream, group, entry_id)
                    except Exception as exc:
                        log.error("Handler error entry=%s: %s", entry_id, exc)
        except redis_lib.exceptions.TimeoutError:
            log.debug("Stream read timed out stream=%s (nothing to read); polling again", stream)    # not an error: just poll again, no back-off
        except Exception as exc:
            log.warning("Stream read error stream=%s: %s", stream, exc)
            _pause(5, stop)


# ── Handlers ──────────────────────────────────────────────────────────────────

def _handle_notification(msg: dict) -> None:
    """In-app notifications are written to the database by the domain services themselves (backend/services/notifications.py); this stream is the delivery hook
    (web push / email later). Today it only logs."""
    log.info("NOTIFICATION → user=%s title=%r", msg.get("user_id"), msg.get("title"))


def _handle_ai_job(msg: dict) -> None:
    """Async AI enrichment of a new case: AI-3 recommendation and AI-2 duplicate candidates (backend/services/ai_jobs.py)."""
    job_type, case_id = msg.get("job_type"), msg.get("case_id")
    if not job_type or not case_id:
        return
    from backend.services.ai_jobs import run_job
    log.info("AI_JOB → %s %s: %s", job_type, case_id, run_job(job_type, case_id))


def _handle_audit(msg: dict) -> None:
    """Audit rows are written synchronously with the action they describe; the stream is for subscribers (dashboards, SIEM)."""
    log.info("AUDIT → actor=%s action=%s resource=%s", msg.get("actor_id"), msg.get("action"), msg.get("resource_id"))


def _handle_sync(msg: dict) -> None:
    """``/sync/mutations`` applies every mutation synchronously (the client needs the per-mutation result); the stream is kept for subscribers."""
    log.info("SYNC → mutation_type=%s actor=%s key=%s", msg.get("mutation_type"), msg.get("actor_id"), msg.get("idempotency_key"))


# ── Startup ───────────────────────────────────────────────────────────────────

def _launch(stream: str, group: str, consumer_name: str, handler: Callable) -> None:
    t = threading.Thread(
        target=_stream_worker,
        args=(stream, group, consumer_name, handler),
        daemon=True,
        name=f"worker-{consumer_name}",
    )
    t.start()
    _threads.append(t)
    log.info("Launched worker thread: %s", t.name)


def start_background_workers() -> None:
    """Start all background worker threads. Call once at application startup."""
    _launch(STREAM_NOTIFICATIONS, GROUP_NOTIFICATIONS, "notif-1",  _handle_notification)
    _launch(STREAM_AI_JOBS,       GROUP_AI_WORKERS,    "ai-1",     _handle_ai_job)
    _launch(STREAM_AUDIT,         GROUP_AUDIT_WRITERS, "audit-1",  _handle_audit)
    _launch(STREAM_SYNC,          GROUP_SYNC_WORKERS,  "sync-1",   _handle_sync)
    from backend.events.push_worker import start_push_worker
    from backend.events.scan_worker import start_scan_worker
    start_push_worker()       # WP5: Expo push delivery of PENDING notifications and their receipts
    start_scan_worker()       # WP6: malware scan of PENDING evidence (does nothing unless SCAN_ENABLED)
    log.info("All background event workers started (%d threads).", len(_threads))
