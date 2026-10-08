"""The rate limiter, the sign-in failure counter and the AI daily budget against a REAL Redis (the unit tests use a fake one).

Skipped unless ``TEST_REDIS_URL`` points at a reachable server AND a non-zero database (the database is flushed before and after: never point this at db 0). The daily/minute windows
use the real server's key expiry; the windows themselves are moved with the fake clock of ``backend.core.rate_limit``.
"""
import os
import time

import pytest
import redis as redis_lib

from backend.ai_gateway.providers.budget import BudgetSpent, Limits, ModelBudgets
from backend.core import rate_limit as rl
from backend.core.config import settings

URL = os.environ.get("TEST_REDIS_URL", "")


def _connect():
    if not URL:
        pytest.skip("TEST_REDIS_URL is not set (needs a real Redis, database number > 0)")
    client = redis_lib.from_url(URL, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
    if client.connection_pool.connection_kwargs.get("db", 0) == 0:
        pytest.skip("TEST_REDIS_URL must name a database other than 0 (the tests flush it)")
    try:
        client.ping()
    except redis_lib.exceptions.RedisError as exc:
        pytest.skip(f"no Redis reachable at TEST_REDIS_URL: {type(exc).__name__}")
    return client


@pytest.fixture
def real():
    client = _connect()
    client.flushdb()
    yield client
    client.flushdb()


class Clock:
    def __init__(self, t=1_700_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    c = Clock()
    monkeypatch.setattr(rl, "_clock", c)
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "dev")
    rl.limiter.reset()
    yield c
    rl.limiter.reset()


def use(monkeypatch, client):
    monkeypatch.setattr(rl, "_redis", lambda: client)


# ---------------------------------------------------------------- fixed-window counters
def test_counters_use_incr_with_a_real_expiry_and_are_shared_between_instances(real, monkeypatch):
    use(monkeypatch, real)
    a, b = rl.RateLimiter(), rl.RateLimiter()                          # two "processes"
    assert [a.hit("login", "ip:1.2.3.4", 60)[0], b.hit("login", "ip:1.2.3.4", 60)[0], a.hit("login", "ip:1.2.3.4", 60)[0]] == [1, 2, 3]
    keys = real.keys("civic:rl:login:ip:1.2.3.4:*")
    assert len(keys) == 1 and real.get(keys[0]) == "3"
    assert 55 <= real.ttl(keys[0]) <= 61                               # window + 1 s, set by the real EXPIRE
    other = a.hit("login", "ip:9.9.9.9", 60)[0]
    assert other == 1                                                  # another subject has its own counter


def test_a_new_window_is_a_new_key(real, monkeypatch, _on):
    use(monkeypatch, real)
    lim = rl.RateLimiter()
    assert lim.hit("r", "u:1", 60)[0] == 1 and lim.hit("r", "u:1", 60)[0] == 2
    _on.t += 61
    assert lim.hit("r", "u:1", 60)[0] == 1
    assert len(real.keys("civic:rl:r:u:1:*")) == 2


# ---------------------------------------------------------------- sign-in failure counter (sorted set)
def test_failure_counter_sliding_window_on_a_real_sorted_set(real, monkeypatch, _on):
    use(monkeypatch, real)
    fc, other = rl.FailureCounter(window_s=60, namespace="t"), rl.FailureCounter(window_s=60, namespace="t")
    for _ in range(3):
        fc.add("alice@example.test")
    _on.t += 30
    other.add("alice@example.test")                                    # a second process sees the same failures
    assert fc.count("alice@example.test") == 4 and other.count("alice@example.test") == 4
    assert 29 <= fc.retry_after("alice@example.test") <= 31
    _on.t += 31                                                        # the first three are 61 s old, the last one 31 s
    assert fc.count("alice@example.test") == 1
    fc.clear("alice@example.test")
    assert other.count("alice@example.test") == 0 and not real.keys("civic:rl:t:*")


# ---------------------------------------------------------------- the AI daily budget
def test_the_daily_ai_budget_is_shared_through_real_redis(real):
    clock = Clock()
    a = ModelBudgets({"m": Limits(rpd=3)}, provider="gemini", clock=clock, sleep=lambda s: None, redis_getter=lambda: real)
    b = ModelBudgets({"m": Limits(rpd=3)}, provider="gemini", clock=clock, sleep=lambda s: None, redis_getter=lambda: real)
    a.acquire("m"); b.acquire("m"); a.acquire("m")
    with pytest.raises(BudgetSpent):
        b.acquire("m")
    key = real.keys("civic:aibudget:rpd:gemini:m:*")[0]
    assert real.get(key) == "3" and 26 * 3600 - 60 <= real.ttl(key) <= 26 * 3600


# ---------------------------------------------------------------- through the real application with a real Redis
def test_the_real_app_limits_with_real_redis_and_the_signin_lockout_is_shared(real, monkeypatch, staffed):
    from fastapi.testclient import TestClient

    from backend.main import app
    from backend.services import auth as auth_service
    use(monkeypatch, real)
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT_PER_MIN", 3)
    auth_service.reset_throttle()
    c = TestClient(app, raise_server_exceptions=False)
    h = staffed.headers("alice")
    assert [c.get("/api/v1/me", headers=h).status_code for _ in range(3)] == [200, 200, 200]
    r = c.get("/api/v1/me", headers=h)
    assert r.status_code == 429 and r.json()["error"]["code"] == "RATE_LIMITED" and int(r.headers["retry-after"]) >= 1
    uid = staffed.users["alice"]["id"]
    assert real.get(real.keys(f"civic:rl:default:u:{uid}:*")[0]) == "4"
    for _ in range(auth_service.MAX_FAILURES):
        c.post("/api/v1/auth/login", json={"identifier": "bob@example.test", "password": "wrong"})
    assert real.zcard("civic:rl:signin:bob@example.test") == auth_service.MAX_FAILURES        # the lockout lives in Redis, not in the process
    auth_service.reset_throttle()
    real.delete("civic:rl:signin:bob@example.test")


# ---------------------------------------------------------------- a real server that is gone
def test_an_unreachable_server_falls_back_to_the_process_and_still_limits(monkeypatch, caplog):
    dead = redis_lib.from_url("redis://127.0.0.1:6399/15", socket_connect_timeout=0.3, socket_timeout=0.3)
    use(monkeypatch, dead)
    lim = rl.RateLimiter()
    with caplog.at_level("WARNING", logger="civicconnect.ratelimit"):
        assert [lim.hit("r", "u:1", 60)[0] for _ in range(3)] == [1, 2, 3]
    assert len([r for r in caplog.records if "per-process counters" in r.getMessage()]) == 1
    t0 = time.monotonic()
    lim.hit("r", "u:1", 60)
    assert time.monotonic() - t0 < 0.25                                # the back-off: no new dead-socket wait on every request
