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
    """
    Deliver in-app notification.
    In production: write to DB + push via WebSocket / FCM / APNs.
    """
    log.info(
        "NOTIFICATION → user=%s title=%r",
        msg.get("user_id"), msg.get("title"),
    )
    # TODO: db.add(Notification(...)) + push gateway call


def _handle_ai_job(msg: dict) -> None:
    """
    Run an async AI analysis job from the queue.
    In production: call AIService methods and persist AIAnalysis row.
    """
    job_type = msg.get("job_type")
    case_id  = msg.get("case_id")
    log.info("AI_JOB → job_type=%s case_id=%s", job_type, case_id)
    # TODO: ai_service.analyze_intake / triage / fusion then persist


def _handle_audit(msg: dict) -> None:
    """Write an audit event to the database."""
    log.info(
        "AUDIT → actor=%s action=%s resource=%s",
        msg.get("actor_id"), msg.get("action"), msg.get("resource_id"),
    )
    # TODO: db.add(AuditEvent(...))


def _handle_sync(msg: dict) -> None:
    """
    Replay an offline mutation from the citizen PWA.
    Idempotency key prevents double-application.
    """
    log.info(
        "SYNC → mutation_type=%s actor=%s key=%s",
        msg.get("mutation_type"), msg.get("actor_id"), msg.get("idempotency_key"),
    )
    # TODO: Check idempotency key in DB; if unseen → apply mutation


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
