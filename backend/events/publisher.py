"""
Redis Streams event architecture for CivicConnect v2.

Streams used:
  civic:notifications    - push notification events to users
  civic:ai_jobs          - async AI intake/triage/fusion jobs
  civic:audit            - audit log propagation
  civic:sync             - offline mutation replay from citizen app

All publishers are fire-and-forget and degrade gracefully when Redis is
unavailable (logs a warning, never raises, never breaks the HTTP response).
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import redis as redis_lib

from backend.core.config import settings
from backend.core.telemetry import inject_trace_context, producer_span

log = logging.getLogger("civicconnect.events")

# ── Singleton Redis client (lazy, fault-tolerant) ─────────────────────────────
_redis_client: redis_lib.Redis | None = None
_redis_down_until: float = 0.0          # after a failed connection attempt, do not retry (and block for the timeout) on every event
REDIS_RETRY_SECONDS = 30.0


PUBLISH_CONNECT_TIMEOUT_S = 2.0         # a request must never wait long for a Redis that is down
PUBLISH_SOCKET_TIMEOUT_S = 5.0          # redis-py >= 8 defaults to 5 s; explicit so the value does not depend on the library version
HEALTH_CHECK_INTERVAL_S = 30            # ping connections idle for longer than this before reusing them (stale after a Redis restart)


def make_client(*, connect_timeout: float, socket_timeout: float, health_check_interval: int = HEALTH_CHECK_INTERVAL_S) -> redis_lib.Redis:
    """A Redis client with explicit timeouts (the publish path and the blocking worker readers need different ones)."""
    return redis_lib.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=connect_timeout,
        socket_timeout=socket_timeout,
        health_check_interval=health_check_interval,
    )


def get_redis() -> redis_lib.Redis | None:
    """Return a Redis client, or None if the server is unreachable."""
    global _redis_client
    global _redis_down_until
    if _redis_client is not None:
        return _redis_client
    if time.monotonic() < _redis_down_until:
        return None
    try:
        client = make_client(connect_timeout=PUBLISH_CONNECT_TIMEOUT_S, socket_timeout=PUBLISH_SOCKET_TIMEOUT_S)
        client.ping()
        _redis_client = client
        log.info("Redis connected: %s", settings.REDIS_URL)
        return _redis_client
    except Exception as exc:
        _redis_down_until = time.monotonic() + REDIS_RETRY_SECONDS
        log.warning("Redis unavailable (%s); event publishing is disabled for %.0fs.", exc, REDIS_RETRY_SECONDS)
        return None


# ── Stream names ──────────────────────────────────────────────────────────────
STREAM_NOTIFICATIONS = "civic:notifications"
STREAM_AI_JOBS       = "civic:ai_jobs"
STREAM_AUDIT         = "civic:audit"
STREAM_SYNC          = "civic:sync"

# Consumer group names
GROUP_NOTIFICATIONS  = "notification-workers"
GROUP_AI_WORKERS     = "ai-workers"
GROUP_AUDIT_WRITERS  = "audit-writers"
GROUP_SYNC_WORKERS   = "sync-workers"


# ── Generic publisher ─────────────────────────────────────────────────────────
def publish(stream: str, payload: dict[str, Any]) -> str | None:
    """
    Publish *payload* to a Redis Stream.

    Returns the entry ID on success, None on failure.
    Failure is non-fatal: the calling request still succeeds.
    """
    r = get_redis()
    if r is None:
        return None
    try:
        # Redis XADD requires string values
        flat = {k: json.dumps(v) if not isinstance(v, str) else v
                for k, v in payload.items()}
        flat["_ts"] = str(int(time.time() * 1000))
        with producer_span(stream):                     # WP8: no-ops while OTEL_ENABLED is false
            inject_trace_context(flat)                  # traceparent / tracestate fields: the worker continues this trace
            entry_id = r.xadd(stream, flat)
        log.debug("Event published stream=%s id=%s", stream, entry_id)
        return entry_id
    except Exception as exc:
        log.warning("Failed to publish event to %s: %s", stream, exc)
        return None


# ── Typed publishers ──────────────────────────────────────────────────────────

def emit_notification(
    user_id: str,
    title: str,
    content: str,
    entity_type: str = "",
    entity_id: str = "",
) -> str | None:
    """Push a notification event for a specific user."""
    return publish(STREAM_NOTIFICATIONS, {
        "event_type": "notification",
        "user_id": user_id,
        "title": title,
        "content": content,
        "entity_type": entity_type,
        "entity_id": entity_id,
    })


def emit_ai_job(
    job_type: str,          # "intake" | "fusion" | "triage"
    case_id: str | None,
    report_id: str | None,
    payload: dict,
) -> str | None:
    """Enqueue an async AI analysis job."""
    return publish(STREAM_AI_JOBS, {
        "event_type": "ai_job",
        "job_type": job_type,
        "case_id": case_id or "",
        "report_id": report_id or "",
        "payload": payload,
    })


def emit_audit(
    actor_id: str,
    action: str,            # e.g. "case.status_updated"
    resource_id: str = "",
    details: dict | None = None,
) -> str | None:
    """Propagate an audit event for compliance / timeline display."""
    return publish(STREAM_AUDIT, {
        "event_type": "audit",
        "actor_id": actor_id,
        "action": action,
        "resource_id": resource_id,
        "details": details or {},
    })


def emit_sync_mutation(
    idempotency_key: str,
    mutation_type: str,     # "create_case" | "add_evidence" | "support"
    actor_id: str,
    data: dict,
) -> str | None:
    """Replay an offline mutation from the citizen PWA sync queue."""
    return publish(STREAM_SYNC, {
        "event_type": "sync_mutation",
        "idempotency_key": idempotency_key,
        "mutation_type": mutation_type,
        "actor_id": actor_id,
        "data": data,
    })


# ── Consumer group bootstrap ──────────────────────────────────────────────────
def ensure_consumer_groups() -> None:
    """
    Create all consumer groups if they don't already exist.
    Safe to call multiple times (uses MKSTREAM + ignores BUSYGROUP).
    Call this once at application startup.
    """
    r = get_redis()
    if r is None:
        log.warning("Skipping consumer group setup: Redis unavailable.")
        return

    groups = [
        (STREAM_NOTIFICATIONS, GROUP_NOTIFICATIONS),
        (STREAM_AI_JOBS,       GROUP_AI_WORKERS),
        (STREAM_AUDIT,         GROUP_AUDIT_WRITERS),
        (STREAM_SYNC,          GROUP_SYNC_WORKERS),
    ]
    for stream, group in groups:
        try:
            r.xgroup_create(stream, group, id="$", mkstream=True)
            log.info("Consumer group created: stream=%s group=%s", stream, group)
        except redis_lib.exceptions.ResponseError as exc:
            if "BUSYGROUP" in str(exc):
                log.debug("Consumer group already exists: %s/%s", stream, group)
            else:
                log.warning("Failed to create consumer group %s/%s: %s", stream, group, exc)
