"""Rate limiting (WP3): fixed-window counters in Redis (INCR + EXPIRE) with an in-process fallback, and one global FastAPI dependency.

* ``rate_limit_dependency`` classifies the request (method + path below ``API_V1_STR``) with ``RULES``, keys it by user id (token ``sub``, no database
  hit) or client IP, sets ``X-RateLimit-Limit/Remaining/Reset`` and raises ``RATE_LIMITED`` (429, ``Retry-After``) when the window is used up.
  Register it once: ``FastAPI(..., dependencies=[Depends(rate_limit_dependency)])``.
* Redis down or erroring: the same counters live in process memory (per worker, bounded), and a warning is logged at most once a minute. Never fail open silently.
* ``FailureCounter`` is the shared sliding-window failure count behind the sign-in lockout.
* Behind a proxy or tunnel every client shares the peer address: set ``RATE_LIMIT_TRUST_FORWARDED_FOR=true`` there (rightmost X-Forwarded-For entry) or the per-IP
  login and register limits are shared by everybody.
* Off when ``RATE_LIMIT_ENABLED=false`` or ``ENVIRONMENT=test``. ``X-RateLimit-Reset`` is the epoch second at which the window ends.
"""
from __future__ import annotations

import hashlib
import ipaddress
import logging
import math
import re
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Optional

from fastapi import Request, Response

from backend.core.config import settings
from backend.core.exceptions import CivicConnectException

log = logging.getLogger("civicconnect.ratelimit")

WARN_EVERY_S = 60.0                 # Redis-fallback warning cadence
REDIS_BACKOFF_S = 10.0              # after a Redis error, use the fallback for this long instead of waiting on a dead socket for every request
CLEANUP_EVERY_S = 30.0              # lazy purge of expired in-process windows
MAX_LOCAL_KEYS = 50_000             # hard bound on the in-process tables (a purge runs first; if still above, the oldest are dropped)
KEY_PREFIX = "civic:rl"

_clock: Callable[[], float] = time.time     # tests replace this with a fake clock


def _now() -> float:
    return _clock()


def _redis():
    """The shared Redis client or None (the publisher keeps its own back-off for a server that is down)."""
    from backend.events import publisher
    return publisher.get_redis()


_warn_lock = threading.Lock()
_warned_at = -1e18                  # one warning per WARN_EVERY_S for the whole process, not per limiter instance


def _warn_once(message: str) -> None:
    global _warned_at
    with _warn_lock:
        now = _now()
        if now - _warned_at < WARN_EVERY_S:
            return
        _warned_at = now
    log.warning(message)


class _Backend:
    """Redis-or-memory plumbing shared by the limiter and the failure counter: the client, the error back-off and the once-a-minute warning."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self._skip_redis_until = -1e18

    def client(self):
        if _now() < self._skip_redis_until:
            return None
        r = _redis()
        if r is None:
            self._warn("Redis is unreachable")
        return r

    def failed(self, exc: Exception) -> None:
        self._skip_redis_until = _now() + REDIS_BACKOFF_S
        self._warn(f"Redis error ({exc.__class__.__name__})")

    def _warn(self, why: str) -> None:
        _warn_once(f"{why}: rate limits fall back to per-process counters (not shared between workers).")

    def reset(self) -> None:
        global _warned_at
        with self.lock:
            self._skip_redis_until = -1e18
        with _warn_lock:
            _warned_at = -1e18


class RateLimiter:
    """Fixed-window counter: ``hit`` increments the window for (rule, subject) and returns ``(count, window_end_epoch)``."""

    def __init__(self) -> None:
        self._b = _Backend()
        self._local: dict[str, tuple[int, float]] = {}       # key -> (count, window end)
        self._last_cleanup = 0.0

    def hit(self, rule: str, subject: str, window_s: int) -> tuple[int, float]:
        now = _now()
        start = math.floor(now / window_s) * window_s
        end = start + window_s
        key = f"{KEY_PREFIX}:{rule}:{subject}:{int(start)}"
        r = self._b.client()
        if r is not None:
            try:
                pipe = r.pipeline()
                pipe.incr(key)
                pipe.expire(key, int(window_s) + 1)           # every hit re-arms the expiry: no INCR-without-TTL leak if the first EXPIRE were lost
                return int(pipe.execute()[0]), end
            except Exception as exc:
                self._b.failed(exc)
        return self._hit_local(key, now, end), end

    def _hit_local(self, key: str, now: float, end: float) -> int:
        with self._b.lock:
            if now - self._last_cleanup >= CLEANUP_EVERY_S or len(self._local) > MAX_LOCAL_KEYS:
                self._local = {k: v for k, v in self._local.items() if v[1] > now}
                if len(self._local) > MAX_LOCAL_KEYS:
                    self._local = dict(sorted(self._local.items(), key=lambda kv: kv[1][1])[len(self._local) // 2:])
                self._last_cleanup = now
            count = (self._local[key][0] if key in self._local and self._local[key][1] > now else 0) + 1
            self._local[key] = (count, end)
            return count

    def reset(self) -> None:
        with self._b.lock:
            self._local.clear()
            self._last_cleanup = 0.0
        self._b.reset()


class FailureCounter:
    """Sliding-window failure count per key (the sign-in lockout): ``add`` a failure, ``count`` those in the last ``window_s``, ``clear`` on success."""

    def __init__(self, window_s: int = 60, namespace: str = "fail") -> None:
        self.window_s = window_s
        self.ns = namespace
        self._b = _Backend()
        self._local: dict[str, list[float]] = {}

    @staticmethod
    def _norm(key: str) -> str:
        """Identifiers come from the request body: bound their length so a long one cannot bloat Redis keys or the in-process table."""
        return key if len(key) <= 128 else hashlib.sha256(key.encode("utf-8")).hexdigest()

    def _key(self, key: str) -> str:
        return f"{KEY_PREFIX}:{self.ns}:{key}"

    def _bound(self, now: float) -> None:
        if len(self._local) > MAX_LOCAL_KEYS:
            self._local = {k: v for k, v in self._local.items() if any(now - t < self.window_s for t in v)}
            if len(self._local) > MAX_LOCAL_KEYS:                       # still too many live keys: keep the most recently failed half
                self._local = dict(sorted(self._local.items(), key=lambda kv: kv[1][-1])[len(self._local) // 2:])

    def _recent(self, key: str, now: float) -> list[float]:
        recent = [t for t in self._local.get(key, []) if now - t < self.window_s]
        if recent:
            self._local[key] = recent
        else:
            self._local.pop(key, None)        # lazy cleanup: a key with no live failures takes no memory
        return recent

    def count(self, key: str) -> int:
        key = self._norm(key)
        now = _now()
        r = self._b.client()
        if r is not None:
            try:
                k = self._key(key)
                pipe = r.pipeline()
                pipe.zremrangebyscore(k, 0, now - self.window_s)
                pipe.zcard(k)
                return int(pipe.execute()[1])
            except Exception as exc:
                self._b.failed(exc)
        with self._b.lock:
            return len(self._recent(key, now))

    def add(self, key: str) -> None:
        key = self._norm(key)
        now = _now()
        r = self._b.client()
        if r is not None:
            try:
                k = self._key(key)
                pipe = r.pipeline()
                pipe.zadd(k, {f"{now}:{uuid.uuid4().hex[:8]}": now})
                pipe.expire(k, int(self.window_s) + 1)
                pipe.execute()
                return
            except Exception as exc:
                self._b.failed(exc)
        with self._b.lock:
            self._recent(key, now)
            self._local.setdefault(key, []).append(now)
            self._bound(now)

    def retry_after(self, key: str) -> int:
        """Seconds until the oldest failure in the window expires (0 when there is none)."""
        key = self._norm(key)
        now = _now()
        r = self._b.client()
        if r is not None:
            try:
                oldest = r.zrange(self._key(key), 0, 0, withscores=True)
                return max(0, math.ceil(self.window_s - (now - oldest[0][1]))) if oldest else 0
            except Exception as exc:
                self._b.failed(exc)
        with self._b.lock:
            recent = self._recent(key, now)
            return max(0, math.ceil(self.window_s - (now - recent[0]))) if recent else 0

    def clear(self, key: str) -> None:
        key = self._norm(key)
        r = self._b.client()
        if r is not None:
            try:
                r.delete(self._key(key))
            except Exception as exc:
                self._b.failed(exc)
        with self._b.lock:
            self._local.pop(key, None)

    def reset(self) -> None:
        """Forget everything in process (tests); Redis keys expire on their own."""
        with self._b.lock:
            self._local.clear()
        self._b.reset()


limiter = RateLimiter()


@dataclass(frozen=True)
class Rule:
    name: str
    method: str
    pattern: re.Pattern
    limit_attr: str
    window_s: int
    by: str                    # "ip": always the client address; "user": the token subject, else the client address


_MIN, _HOUR = 60, 3600


def _r(name: str, method: str, pattern: str, attr: str, window: int, by: str) -> Rule:
    return Rule(name, method, re.compile(pattern), attr, window, by)


# First match wins. Paths are relative to API_V1_STR with the trailing slash removed.
RULES: tuple[Rule, ...] = (
    _r("login", "POST", r"/auth/(login|token)", "RATE_LIMIT_LOGIN_IP_PER_MIN", _MIN, "ip"),
    _r("register", "POST", r"/auth/register", "RATE_LIMIT_REGISTER_IP_PER_MIN", _MIN, "ip"),
    _r("case_create", "POST", r"/cases", "RATE_LIMIT_CASE_CREATE_PER_HOUR", _HOUR, "user"),
    _r("upload_init", "POST", r"/evidence/upload-init", "RATE_LIMIT_UPLOAD_INIT_PER_HOUR", _HOUR, "user"),
    _r("ai", "POST", r"/cases/intake/analyze|/cases/[^/]+/(fusion|triage)/analyze|/copilot/query|/analytics/explain", "RATE_LIMIT_AI_PER_HOUR", _HOUR, "user"),
)
DEFAULT_RULE = Rule("default", "*", re.compile(".*"), "RATE_LIMIT_DEFAULT_PER_MIN", _MIN, "user")
_EXEMPT = re.compile(r"/health(/.*)?")                          # health probes only: everything else, including the anonymous signed-media PUT, is counted (by IP)


def _relative_path(request: Request) -> Optional[str]:
    """Path below the API prefix with no trailing slash, or None when the request is not under it (root, docs)."""
    path = request.scope.get("path", "")
    prefix = settings.API_V1_STR.rstrip("/")
    if path == f"{prefix}/openapi.json":
        return None
    if path.startswith(prefix + "/") or path == prefix:
        return path[len(prefix):].rstrip("/") or "/"
    return None


def classify(method: str, rel_path: str) -> Optional[Rule]:
    """The rule for a request, or None when it is exempt."""
    if method == "OPTIONS" or _EXEMPT.fullmatch(rel_path):
        return None
    for rule in RULES:
        if rule.method == method and rule.pattern.fullmatch(rel_path):
            return rule
    return DEFAULT_RULE


def client_ip(request: Request) -> str:
    """The socket peer, or (RATE_LIMIT_TRUST_FORWARDED_FOR, behind a proxy or tunnel you control) the RIGHTMOST X-Forwarded-For entry: that is the one the trusted proxy
    appended; everything to its left is client-controlled and can be forged. Anything that is not an IP address is ignored."""
    peer = (request.client.host if request.client else "unknown")[:64]
    if settings.RATE_LIMIT_TRUST_FORWARDED_FOR:
        last = request.headers.get("x-forwarded-for", "").split(",")[-1].strip()
        try:
            return str(ipaddress.ip_address(last))
        except ValueError:
            pass
    return peer


def _token_subject(request: Request) -> Optional[str]:
    """The ``sub`` claim of a valid bearer token (signature and expiry checked, no database), else None."""
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    from backend.core.security import decode_token
    try:
        return str(decode_token(token.strip())["sub"])
    except Exception:
        return None


def enabled() -> bool:
    return bool(settings.RATE_LIMIT_ENABLED) and settings.ENVIRONMENT != "test"


def rate_limit_dependency(request: Request, response: Response) -> None:
    """Global dependency: count the request against its rule, set the ``X-RateLimit-*`` headers, answer 429 when the limit is used up."""
    if not enabled():
        return
    rel = _relative_path(request)
    if rel is None:
        return
    rule = classify(request.method, rel)
    if rule is None:
        return
    sub = _token_subject(request) if rule.by == "user" else None
    subject = f"u:{sub}" if sub else f"ip:{client_ip(request)}"
    limit = int(getattr(settings, rule.limit_attr))
    count, reset_at = limiter.hit(rule.name, subject, rule.window_s)
    remaining = max(0, limit - count)
    headers = {"X-RateLimit-Limit": str(limit), "X-RateLimit-Remaining": str(remaining), "X-RateLimit-Reset": str(int(math.ceil(reset_at)))}
    if count > limit:
        retry = max(1, math.ceil(reset_at - _now()))
        raise CivicConnectException("RATE_LIMITED", "Too many requests. Please slow down and try again later.", 429,
                                    {"retry_after_seconds": retry, "limit": limit, "window_seconds": rule.window_s, "rule": rule.name},
                                    headers={**headers, "Retry-After": str(retry)})
    response.headers.update(headers)
