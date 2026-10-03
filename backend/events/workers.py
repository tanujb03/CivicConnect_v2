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

from backend.events.publisher import (
    STREAM_AI_JOBS, STREAM_AUDIT, STREAM_NOTIFICATIONS, STREAM_SYNC,
    GROUP_AI_WORKERS, GROUP_AUDIT_WRITERS, GROUP_NOTIFICATIONS, GROUP_SYNC_WORKERS,
    get_redis,
)

log = logging.getLogger("civicconnect.workers")

WORKER_BLOCK_MS = 5_000   # block 5 s waiting for new messages
WORKER_COUNT_PER_STREAM = 1

_threads: list[threading.Thread] = []


# ── Generic stream reader ─────────────────────────────────────────────────────

def _stream_worker(
    stream: str,
    group: str,
    consumer_name: str,
    handler: Callable[[dict], None],
) -> None:
    """Read messages from a Redis Stream consumer group and call *handler*."""
    log.info("Worker starting: stream=%s consumer=%s", stream, consumer_name)
    while True:
        r = get_redis()
        if r is None:
            time.sleep(10)
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
                        handler(decoded)
                        r.xack(stream, group, entry_id)
                    except Exception as exc:
                        log.error("Handler error entry=%s: %s", entry_id, exc)
        except Exception as exc:
            log.warning("Stream read error stream=%s: %s", stream, exc)
            time.sleep(5)


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
    log.info("All background event workers started (%d threads).", len(_threads))
