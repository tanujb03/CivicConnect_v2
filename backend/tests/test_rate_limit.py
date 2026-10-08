"""WP3 rate limiting: classification, fixed windows with an injected clock, the Redis counters (fake server) and the in-process fallback, the failure counter,
and the real v1 router behind the dependency (mounted here on a private app; main.py registers it globally). No real Redis, no sleeping."""
from __future__ import annotations

import logging

import pytest
import redis as redis_lib
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.core import rate_limit as rl
from backend.core.config import settings
from backend.core.exceptions import (
    CivicConnectException,
    civicconnect_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)

T0 = 3_600_000.0       # a multiple of a minute and of an hour, so windows start exactly here


class Clock:
    def __init__(self, t: float = T0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, s: float) -> None:
        self.t += s


class FakePipe:
    def __init__(self, server: "FakeRedis"):
        self.s, self.ops = server, []

    def __getattr__(self, name):
        def queue(*a, **k):
            self.ops.append((name, a, k))
            return self
        return queue

    def execute(self):
        return [getattr(self.s, n)(*a, **k) for n, a, k in self.ops]


class FakeRedis:
    """The few commands the limiter uses: incr/expire/ttl, sorted sets, delete, pipeline. Expiry follows the injected clock."""

    def __init__(self, clock: Clock):
        self.clock, self.data, self.exp = clock, {}, {}

    def _live(self, key):
        if key in self.exp and self.exp[key] <= self.clock():
            self.data.pop(key, None)
            self.exp.pop(key, None)
        return key in self.data

    def pipeline(self):
        return FakePipe(self)

    def incr(self, key):
        self._live(key)
        self.data[key] = int(self.data.get(key, 0)) + 1
        return self.data[key]

    def expire(self, key, seconds):
        if not self._live(key):
            return False
        self.exp[key] = self.clock() + seconds
        return True

    def ttl(self, key):
        return int(self.exp[key] - self.clock()) if self._live(key) and key in self.exp else -1

    def zadd(self, key, mapping):
        self._live(key)
        self.data.setdefault(key, {}).update(mapping)

    def zremrangebyscore(self, key, lo, hi):
        if self._live(key):
            self.data[key] = {m: s for m, s in self.data[key].items() if not lo <= s <= hi}

    def zcard(self, key):
        return len(self.data[key]) if self._live(key) else 0

    def zrange(self, key, start, stop, withscores=False):
        items = sorted(self.data[key].items(), key=lambda kv: kv[1]) if self._live(key) else []
        return [(m, s) for m, s in items[start:stop + 1]]

    def delete(self, key):
        self.exp.pop(key, None)
        return 1 if self.data.pop(key, None) is not None else 0


class DownRedis:
    """A client whose server is gone: every command (also inside a pipeline) raises ConnectionError."""
    calls = 0

    def pipeline(self):
        DownRedis.calls += 1
        raise redis_lib.exceptions.ConnectionError("connection refused")

    def __getattr__(self, name):
        def boom(*a, **k):
            DownRedis.calls += 1
            raise redis_lib.exceptions.ConnectionError("connection refused")
        return boom


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(rl, "_clock", c)
    return c


@pytest.fixture(autouse=True)
def _fresh(monkeypatch, clock):
    """Limiter on, in-process counters (no Redis) unless a test installs one, clean state before and after."""
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "dev")
    monkeypatch.setattr(rl, "_redis", lambda: None)
    rl.limiter.reset()
    DownRedis.calls = 0
    yield
    rl.limiter.reset()


def use_redis(monkeypatch, server):
    monkeypatch.setattr(rl, "_redis", lambda: server)


# ---------------------------------------------------------------- classification

@pytest.mark.parametrize("method,path,rule", [
    ("POST", "/auth/login", "login"), ("POST", "/auth/token", "login"), ("POST", "/auth/register", "register"),
    ("POST", "/cases", "case_create"), ("POST", "/evidence/upload-init", "upload_init"),
    ("POST", "/cases/intake/analyze", "ai"), ("POST", "/cases/abc-123/fusion/analyze", "ai"), ("POST", "/cases/abc-123/triage/analyze", "ai"),
    ("POST", "/copilot/query", "ai"), ("POST", "/analytics/explain", "ai"),
    ("GET", "/cases", "default"), ("GET", "/cases/abc-123", "default"), ("POST", "/cases/abc-123/triage/decision", "default"),
    ("POST", "/auth/refresh", "default"), ("GET", "/auth/login", "default"), ("GET", "/me", "default"), ("POST", "/evidence", "default"),
])
def test_classify_limited_routes(method, path, rule):
    assert rl.classify(method, path).name == rule


@pytest.mark.parametrize("method,path", [("GET", "/health"), ("GET", "/health/live"), ("GET", "/health/ready"), ("OPTIONS", "/cases")])
def test_classify_exempt_routes(method, path):
    assert rl.classify(method, path) is None


def test_signed_media_routes_are_counted_by_the_default_rule_not_exempt():
    assert rl.classify("PUT", "/evidence/blob/tok").name == "default" and rl.classify("GET", "/evidence/blob/tok").name == "default"


# ---------------------------------------------------------------- the limiter: windows and the clock

def test_fixed_window_counts_and_resets(clock):
    assert [rl.limiter.hit("r", "u:1", 60)[0] for _ in range(3)] == [1, 2, 3]
    assert rl.limiter.hit("r", "u:2", 60)[0] == 1                       # other subject, other counter
    assert rl.limiter.hit("other", "u:1", 60)[0] == 1                   # other rule, other counter
    count, end = rl.limiter.hit("r", "u:1", 60)
    assert (count, end) == (4, T0 + 60)
    clock.advance(59)
    assert rl.limiter.hit("r", "u:1", 60)[0] == 5
    clock.advance(1)                                                    # the next window opens
    assert rl.limiter.hit("r", "u:1", 60)[0] == 1


def test_local_counters_are_bounded_by_lazy_cleanup(clock):
    for i in range(50):
        rl.limiter.hit("r", f"ip:{i}", 60)
    assert len(rl.limiter._local) == 50
    clock.advance(rl.CLEANUP_EVERY_S + 61)
    rl.limiter.hit("r", "ip:new", 60)
    assert len(rl.limiter._local) == 1                                  # expired windows were purged


def test_redis_counters_keys_expiry_and_shared_state(monkeypatch, clock):
    server = FakeRedis(clock)
    use_redis(monkeypatch, server)
    assert [rl.limiter.hit("login", "ip:9.9.9.9", 60)[0] for _ in range(3)] == [1, 2, 3]
    other_worker = rl.RateLimiter()                                     # a second process sees the same counter
    assert other_worker.hit("login", "ip:9.9.9.9", 60)[0] == 4
    (key,) = server.data
    assert key == f"civic:rl:login:ip:9.9.9.9:{int(T0)}"
    assert 0 < server.ttl(key) <= 61                                    # every counter expires
    assert rl.limiter._local == {}                                      # nothing fell back
    clock.advance(61)
    assert rl.limiter.hit("login", "ip:9.9.9.9", 60)[0] == 1            # new window, new key (old one gone)


def test_redis_down_falls_back_still_limits_and_warns_once_a_minute(monkeypatch, clock, caplog):
    use_redis(monkeypatch, DownRedis())
    with caplog.at_level(logging.WARNING, logger="civicconnect.ratelimit"):
        assert [rl.limiter.hit("r", "u:1", 60)[0] for _ in range(3)] == [1, 2, 3]       # still counts (fails closed to local counters)
        assert len([r for r in caplog.records if r.name == "civicconnect.ratelimit"]) == 1
        calls = DownRedis.calls
        rl.limiter.hit("r", "u:1", 60)
        assert DownRedis.calls == calls                                  # back-off: no new attempt on a dead socket for every request
        clock.advance(rl.REDIS_BACKOFF_S + 1)
        rl.limiter.hit("r", "u:1", 60)                                   # Redis retried, failed, but the warning is still rate limited
        assert len(caplog.records) == 1
        clock.advance(rl.WARN_EVERY_S)
        rl.limiter.hit("r", "u:1", 60)
        assert len(caplog.records) == 2


def test_redis_unreachable_none_client_warns_and_uses_local(clock, caplog):
    with caplog.at_level(logging.WARNING, logger="civicconnect.ratelimit"):
        for _ in range(5):
            rl.limiter.hit("r", "u:1", 60)
    assert len(caplog.records) == 1 and "per-process" in caplog.records[0].getMessage()
    assert rl.limiter.hit("r", "u:1", 60)[0] == 6


# ---------------------------------------------------------------- the failure counter (login lockout)

@pytest.fixture(params=["local", "redis", "down"])
def failures(request, monkeypatch, clock):
    if request.param == "redis":
        use_redis(monkeypatch, FakeRedis(clock))
    elif request.param == "down":
        use_redis(monkeypatch, DownRedis())
    fc = rl.FailureCounter(window_s=60)
    yield fc
    fc.reset()


def test_failure_counter_sliding_window_clear_and_reset(failures, clock):
    assert failures.count("a@x") == 0 and failures.retry_after("a@x") == 0
    failures.add("a@x")
    clock.advance(20)
    failures.add("a@x")
    failures.add("b@x")
    assert (failures.count("a@x"), failures.count("b@x")) == (2, 1)
    assert failures.retry_after("a@x") == 40                            # the oldest failure leaves the window in 40 s
    clock.advance(41)
    assert failures.count("a@x") == 1                                   # sliding: only the first one aged out
    clock.advance(20)
    assert (failures.count("a@x"), failures.count("b@x")) == (0, 0)
    failures.add("a@x")
    failures.add("b@x")
    failures.clear("a@x")
    assert (failures.count("a@x"), failures.count("b@x")) == (0, 1)
    failures.reset()
    if not isinstance(rl._redis(), FakeRedis):                          # reset forgets process memory; fake-Redis keys live until they expire
        assert failures.count("b@x") == 0


def test_failure_counter_shared_through_redis(monkeypatch, clock):
    use_redis(monkeypatch, FakeRedis(clock))
    a, b = rl.FailureCounter(), rl.FailureCounter()
    for _ in range(3):
        a.add("k")
    assert b.count("k") == 3
    b.clear("k")
    assert a.count("k") == 0


def test_failure_counter_local_memory_is_cleaned_lazily(clock):
    fc = rl.FailureCounter(window_s=60)
    for i in range(20):
        fc.add(f"k{i}")
    clock.advance(61)
    assert fc.count("k0") == 0
    assert "k0" not in fc._local


# ---------------------------------------------------------------- the exception carries headers

def test_exception_headers_are_merged_and_401_keeps_www_authenticate():
    app = FastAPI()
    app.add_exception_handler(CivicConnectException, civicconnect_exception_handler)

    @app.get("/a")
    def a():
        raise CivicConnectException("X", "m", 429, {"k": 1}, headers={"Retry-After": "7"})

    @app.get("/b")
    def b():
        raise CivicConnectException("AUTH_REQUIRED", "m", 401)

    @app.get("/c")
    def c():
        raise CivicConnectException("NOPE", "m", 404)

    c_ = TestClient(app)
    r = c_.get("/a")
    assert r.status_code == 429 and r.headers["retry-after"] == "7" and r.json()["error"]["details"] == {"k": 1}
    assert c_.get("/b").headers["www-authenticate"] == "Bearer"
    assert "retry-after" not in c_.get("/c").headers


# ---------------------------------------------------------------- the real router behind the dependency

@pytest.fixture
def app(staffed):
    """The real v1 router with the rate-limit dependency, the envelope handlers and a request id (what main.py will do globally)."""
    from backend.api.v1.router import api_router
    a = FastAPI(openapi_url=f"{settings.API_V1_STR}/openapi.json", dependencies=[Depends(rl.rate_limit_dependency)])

    @a.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-ID", "req-test")
        return await call_next(request)

    a.add_exception_handler(CivicConnectException, civicconnect_exception_handler)
    a.add_exception_handler(StarletteHTTPException, http_exception_handler)
    a.add_exception_handler(RequestValidationError, validation_exception_handler)
    a.add_exception_handler(Exception, unhandled_exception_handler)
    a.include_router(api_router, prefix=settings.API_V1_STR)

    @a.get("/")
    def root():
        return {"ok": True}

    return a


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


V1 = "/api/v1"


def burst(client, method, path, n, **kw):
    return [client.request(method, V1 + path, **kw).status_code for _ in range(n)]


def assert_limited(r, limit, window_s=None):
    assert r.status_code == 429
    err = r.json()["error"]
    assert err["code"] == "RATE_LIMITED" and err["request_id"] == "req-test" and err["message"]
    assert err["details"]["limit"] == limit and err["details"]["retry_after_seconds"] >= 1
    if window_s:
        assert err["details"]["window_seconds"] == window_s
    assert r.headers["retry-after"] == str(err["details"]["retry_after_seconds"])
    assert r.headers["x-ratelimit-limit"] == str(limit) and r.headers["x-ratelimit-remaining"] == "0"
    assert int(r.headers["x-ratelimit-reset"]) > T0


@pytest.mark.parametrize("method,path,attr,limit,window,who,body", [
    ("POST", "/auth/login", "RATE_LIMIT_LOGIN_IP_PER_MIN", 3, 60, None, {"identifier": "nobody@example.test", "password": "x"}),
    ("POST", "/auth/token", "RATE_LIMIT_LOGIN_IP_PER_MIN", 3, 60, None, None),
    ("POST", "/auth/register", "RATE_LIMIT_REGISTER_IP_PER_MIN", 2, 60, None, {}),
    ("POST", "/cases", "RATE_LIMIT_CASE_CREATE_PER_HOUR", 2, 3600, "alice", {}),
    ("POST", "/evidence/upload-init", "RATE_LIMIT_UPLOAD_INIT_PER_HOUR", 2, 3600, "alice", {}),
    ("POST", "/cases/intake/analyze", "RATE_LIMIT_AI_PER_HOUR", 2, 3600, "alice", {}),
    ("POST", "/cases/some-case/fusion/analyze", "RATE_LIMIT_AI_PER_HOUR", 2, 3600, "alice", {}),
    ("POST", "/cases/some-case/triage/analyze", "RATE_LIMIT_AI_PER_HOUR", 2, 3600, "alice", {}),
    ("POST", "/copilot/query", "RATE_LIMIT_AI_PER_HOUR", 2, 3600, "alice", {}),
    ("POST", "/analytics/explain", "RATE_LIMIT_AI_PER_HOUR", 2, 3600, "alice", {}),
    ("GET", "/me", "RATE_LIMIT_DEFAULT_PER_MIN", 3, 60, "alice", None),
    ("GET", "/reference/taxonomy", "RATE_LIMIT_DEFAULT_PER_MIN", 3, 60, None, None),
])
def test_each_limited_route_class_answers_429_with_envelope(client, staffed, monkeypatch, method, path, attr, limit, window, who, body):
    monkeypatch.setattr(settings, attr, limit)
    kw = {"headers": staffed.headers(who) if who else {}}
    if body is not None:
        kw["json"] = body
    elif method == "POST":
        kw["data"] = {"username": "nobody", "password": "x"}
    codes = burst(client, method, path, limit, **kw)
    assert 429 not in codes
    r = client.request(method, V1 + path, **kw)
    assert_limited(r, limit, window)


def test_rule_counters_are_independent(client, staffed, monkeypatch):
    """Exhausting the case-create limit leaves reading cases (default rule) and the AI rule untouched."""
    monkeypatch.setattr(settings, "RATE_LIMIT_CASE_CREATE_PER_HOUR", 1)
    h = staffed.headers("alice")
    assert client.post(V1 + "/cases", headers=h, json={}).status_code != 429
    assert client.post(V1 + "/cases", headers=h, json={}).status_code == 429
    assert client.get(V1 + "/me", headers=h).status_code == 200
    assert client.post(V1 + "/copilot/query", headers=h, json={}).status_code != 429


def test_success_responses_carry_the_ratelimit_headers(client, staffed, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT_PER_MIN", 5)
    h = staffed.headers("alice")
    for expected in (4, 3, 2):
        r = client.get(V1 + "/me", headers=h)
        assert r.status_code == 200
        assert r.headers["x-ratelimit-limit"] == "5" and r.headers["x-ratelimit-remaining"] == str(expected)
        assert r.headers["x-ratelimit-reset"] == str(int(T0 + 60))
        assert "retry-after" not in r.headers


def test_window_resets_after_the_window_passes(client, staffed, monkeypatch, clock):
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT_PER_MIN", 2)
    h = staffed.headers("alice")
    assert burst(client, "GET", "/me", 2, headers=h) == [200, 200]
    r = client.get(V1 + "/me", headers=h)
    assert_limited(r, 2)
    assert r.json()["error"]["details"]["retry_after_seconds"] == 60
    clock.advance(30)
    r = client.get(V1 + "/me", headers=h)
    assert r.status_code == 429 and r.headers["retry-after"] == "30"
    clock.advance(30)
    assert client.get(V1 + "/me", headers=h).status_code == 200
    assert client.get(V1 + "/me", headers=h).headers["x-ratelimit-remaining"] == "0"


def test_limits_are_per_user(client, staffed, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT_PER_MIN", 2)
    alice, bob = staffed.headers("alice"), staffed.headers("bob")
    assert burst(client, "GET", "/me", 3, headers=alice) == [200, 200, 429]
    assert burst(client, "GET", "/me", 3, headers=bob) == [200, 200, 429]      # bob has his own budget, same IP
    assert client.get(V1 + "/me", headers=staffed.headers("admin")).status_code == 200


def test_anonymous_and_invalid_tokens_are_keyed_by_ip_login_register_too(client, staffed, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT_PER_MIN", 2)
    assert burst(client, "GET", "/me", 3) == [401, 401, 429]
    # a forged token does not give a fresh budget, it falls back to the same IP key
    assert client.get(V1 + "/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 429
    assert client.get(V1 + "/me", headers={"Authorization": "Basic abc"}).status_code == 429
    # login and register share nothing: separate rules, and one user id cannot dodge an IP rule
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN_IP_PER_MIN", 2)
    h = staffed.headers("alice")
    body = {"identifier": "alice@example.test", "password": "wrong-password"}
    assert 429 not in burst(client, "POST", "/auth/login", 2, json=body, headers=h)
    assert client.post(V1 + "/auth/login", json=body, headers=staffed.headers("bob")).status_code == 429
    r = client.post(V1 + "/auth/register", json={})
    assert r.status_code != 429


def test_forwarded_for_is_honoured_only_when_trusted_and_only_its_rightmost_entry(client, staffed, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT_PER_MIN", 1)
    xff = lambda *hops: {"X-Forwarded-For": ", ".join(hops)}        # noqa: E731
    assert client.get(V1 + "/me", headers=xff("1.1.1.1", "10.0.0.1")).status_code == 401
    assert client.get(V1 + "/me", headers=xff("2.2.2.2", "10.0.0.2")).status_code == 429     # untrusted header: still the one client address
    rl.limiter.reset()
    monkeypatch.setattr(settings, "RATE_LIMIT_TRUST_FORWARDED_FOR", True)
    assert client.get(V1 + "/me", headers=xff("1.1.1.1", "10.0.0.1")).status_code == 401
    assert client.get(V1 + "/me", headers=xff("2.2.2.2", "10.0.0.2")).status_code == 401     # a different address appended by the proxy: another client
    assert client.get(V1 + "/me", headers=xff("3.3.3.3", "10.0.0.1")).status_code == 429     # forged left entries do not buy a fresh bucket
    assert client.get(V1 + "/me", headers=xff("4.4.4.4", "not-an-ip")).status_code == 401    # an unparseable last entry is ignored: the socket peer's own bucket is used
    assert client.get(V1 + "/me", headers=xff("5.5.5.5", "also-not-an-ip")).status_code == 429   # ... and it is one shared bucket, so forging garbage buys nothing


def test_client_ip_ignores_garbage_and_bounds_length(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(settings, "RATE_LIMIT_TRUST_FORWARDED_FOR", True)
    req = lambda xff, host="h" * 200: SimpleNamespace(headers={"x-forwarded-for": xff}, client=SimpleNamespace(host=host))   # noqa: E731
    assert rl.client_ip(req("1.2.3.4, 5.6.7.8")) == "5.6.7.8" and rl.client_ip(req("::1")) == "::1"
    assert rl.client_ip(req("x" * 5000)) == "h" * 64 and rl.client_ip(req("")) == "h" * 64


@pytest.mark.parametrize("path", ["/health", "/health/live", "/health/ready"])
@pytest.mark.parametrize("limit", [0, 1])
def test_health_routes_are_never_limited(client, monkeypatch, path, limit):
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT_PER_MIN", limit)
    for _ in range(5):
        r = client.get(V1 + path)
        assert r.status_code != 429 and "x-ratelimit-limit" not in r.headers
    assert not rl.limiter._local


def test_root_docs_and_openapi_are_exempt_but_the_anonymous_media_put_is_counted(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT_PER_MIN", 0)
    for path in ("/", V1 + "/openapi.json"):
        for _ in range(3):
            r = client.get(path)
            assert r.status_code != 429 and "x-ratelimit-limit" not in r.headers
    assert client.put(V1 + "/evidence/blob/some-token", content=b"x").status_code == 429       # anonymous upload route: counted per IP like any other
    assert client.get(V1 + "/me").status_code == 429                    # a normal route at limit 0 is limited


def test_limiter_in_redis_mode_through_the_router(client, staffed, monkeypatch, clock):
    server = FakeRedis(clock)
    use_redis(monkeypatch, server)
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT_PER_MIN", 2)
    assert burst(client, "GET", "/me", 3, headers=staffed.headers("alice")) == [200, 200, 429]
    assert any(k.startswith("civic:rl:default:u:") for k in server.data) and not rl.limiter._local


def test_redis_down_through_the_router_still_limits(client, staffed, monkeypatch, caplog):
    use_redis(monkeypatch, DownRedis())
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT_PER_MIN", 2)
    with caplog.at_level(logging.WARNING, logger="civicconnect.ratelimit"):
        assert burst(client, "GET", "/me", 4, headers=staffed.headers("alice")) == [200, 200, 429, 429]
    assert len(caplog.records) == 1


@pytest.mark.parametrize("flag,environment", [(False, "dev"), (True, "test")])
def test_switched_off_lets_everything_through(client, staffed, monkeypatch, flag, environment):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", flag)
    monkeypatch.setattr(settings, "ENVIRONMENT", environment)
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT_PER_MIN", 0)
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN_IP_PER_MIN", 0)
    codes = burst(client, "GET", "/me", 3, headers=staffed.headers("alice")) + burst(client, "POST", "/auth/login", 3, json={"identifier": "x@y.z", "password": "p"})
    assert 429 not in codes
    r = client.get(V1 + "/me", headers=staffed.headers("alice"))
    assert r.status_code == 200 and "x-ratelimit-limit" not in r.headers
    assert not rl.limiter._local


def test_expired_token_is_keyed_by_ip(client, staffed, monkeypatch):
    from datetime import timedelta

    from backend.core.security import create_access_token
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT_PER_MIN", 1)
    old = {"Authorization": "Bearer " + create_access_token(staffed.users["alice"]["id"], "citizen", expires_delta=timedelta(minutes=-5))}
    assert client.get(V1 + "/me", headers=old).status_code == 401
    assert client.get(V1 + "/me").status_code == 429            # same IP key as the anonymous caller
    assert client.get(V1 + "/me", headers=staffed.headers("alice")).status_code == 200     # a valid token still has its own user budget


# ---------------------------------------------------------------- the real application (backend.main.app), not a private copy

def test_the_real_app_registers_the_dependency_and_exposes_the_headers():
    from backend.main import app as real_app
    assert rl.rate_limit_dependency in [d.dependency for d in real_app.router.dependencies]
    cors = next(m for m in real_app.user_middleware if m.cls.__name__ == "CORSMiddleware")
    assert {"Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"} <= set(cors.kwargs["expose_headers"])


def test_the_real_app_answers_429_with_the_envelope(staffed, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT_PER_MIN", 2)
    rl.limiter.reset()
    from fastapi.testclient import TestClient

    from backend.main import app as real_app
    c = TestClient(real_app, raise_server_exceptions=False)
    h = staffed.headers("alice")
    assert [c.get(V1 + "/me", headers=h).status_code for _ in range(2)] == [200, 200]
    r = c.get(V1 + "/me", headers=h)
    assert r.status_code == 429 and r.json()["error"]["code"] == "RATE_LIMITED" and int(r.headers["retry-after"]) >= 1 and r.headers["x-ratelimit-remaining"] == "0"
    assert c.get(V1 + "/health/live").status_code == 200
    rl.limiter.reset()
