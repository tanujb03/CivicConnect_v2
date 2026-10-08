"""A model that answered HTTP 429 (free-tier quota) is not called again for a minute: requests degrade at once instead of queueing behind retries and the free-tier spacing."""
import httpx
import pytest

from ai.inference.errors import ProviderUnavailable
from backend.ai_gateway.providers import ChatCompletionsProvider
from backend.ai_gateway.providers import openai_compat as oc


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def build(handler, clock, models=None):
    return ChatCompletionsProvider("gemini", "https://g.test/v1beta/openai", "SECRET-KEY-123", models or {"embedding": "emb-1", "intake": "chat-1"}, max_retries=1,
                                   client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None, clock=clock)


def test_a_429_blocks_that_model_for_the_cooldown_and_then_retries():
    clock, calls = Clock(), []

    def handler(req):
        calls.append(req.url.path)
        return httpx.Response(429, json={"error": {"message": "You exceeded your current quota"}})

    p = build(handler, clock)
    with pytest.raises(ProviderUnavailable, match="HTTP 429"):
        p.embed(["a"])
    assert len(calls) == 2                                           # first call + one retry
    with pytest.raises(ProviderUnavailable, match="cooling down"):
        p.embed(["b"])
    assert len(calls) == 2                                           # no HTTP request while cooling down
    clock.t += oc.QUOTA_COOLDOWN_S + 1
    with pytest.raises(ProviderUnavailable, match="HTTP 429"):
        p.embed(["c"])
    assert len(calls) == 4                                           # tried again after the cooldown


def test_the_cooldown_is_per_model():
    clock = Clock()

    def handler(req):
        import json
        model = json.loads(req.content)["model"]
        if model == "chat-1":
            return httpx.Response(429, json={"error": {"message": "quota"}})
        return httpx.Response(200, json={"model": model, "data": [{"index": 0, "embedding": [1.0, 0.0]}]})

    p = build(handler, clock)
    with pytest.raises(ProviderUnavailable):
        p._post("/chat/completions", json_body={"model": "chat-1", "messages": []})
    assert p.embed(["a"]).vectors == [[1.0, 0.0]]                    # the embedding model has its own quota and keeps working


def test_other_errors_and_successes_do_not_start_a_cooldown():
    clock, n = Clock(), {"c": 0}

    def handler(req):
        n["c"] += 1
        return httpx.Response(503, text="down")

    p = build(handler, clock)
    for _ in range(2):
        with pytest.raises(ProviderUnavailable, match="HTTP 503"):
            p.embed(["a"])
    assert n["c"] == 4 and not p._blocked_until


# ---------------------------------------------------------------- which limit was hit (Gemini QuotaFailure / RetryInfo), recorded shapes
def gemini_429(quota_id, delay=None, model="chat-1"):
    details = [{"@type": "type.googleapis.com/google.rpc.QuotaFailure",
                "violations": [{"quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests", "quotaId": quota_id,
                                "quotaDimensions": {"location": "global", "model": model}, "quotaValue": "20"}]}]
    if delay:
        details.append({"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": delay})
    return [{"error": {"code": 429, "message": "You exceeded your current quota, please check your plan and billing details.", "status": "RESOURCE_EXHAUSTED", "details": details}}]


PER_MINUTE = "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"
PER_DAY = "GenerateRequestsPerDayPerProjectPerModel-FreeTier"


def test_the_429_error_names_the_quota_metric_model_limit_and_retry_delay():
    clock = Clock()
    p = build(lambda req: httpx.Response(429, json=gemini_429(PER_MINUTE, "23s")), clock)
    with pytest.raises(ProviderUnavailable) as e:
        p._post("/chat/completions", json_body={"model": "chat-1", "messages": []})
    msg = str(e.value)
    assert f"quota_id={PER_MINUTE}" in msg and "generate_content_free_tier_requests" in msg and "quota_model=chat-1" in msg and "quota_value=20" in msg and "retry_in=23s" in msg
    assert e.value.quota["retry_delay_s"] == 23.0 and e.value.quota["quota_id"] == PER_MINUTE


def test_parse_quota_error_handles_headers_bare_bodies_and_junk():
    assert oc.parse_quota_error({"error": {"message": "slow down"}}, "7") == {"message": "slow down", "retry_delay_s": 7.0}
    assert oc.parse_quota_error("<html>", None) == {} and oc.parse_quota_error(None, None) == {} and oc.parse_quota_error([], "x") == {}
    assert oc.parse_quota_error(gemini_429(PER_DAY))["quota_id"] == PER_DAY


def test_cooldown_follows_the_retry_delay_for_per_minute_limits(caplog):
    clock, calls = Clock(), []

    def handler(req):
        calls.append(1)
        return httpx.Response(429, json=gemini_429(PER_MINUTE, "23s"))

    def call():
        return p._post("/chat/completions", json_body={"model": "chat-1", "messages": []})

    p = build(handler, clock)
    caplog.set_level("INFO", logger="civicconnect.ai.compat")
    with pytest.raises(ProviderUnavailable):
        call()
    started = [r for r in caplog.records if "cooldown started" in r.getMessage()]
    assert len(started) == 1 and "for 24 s" in started[0].getMessage() and PER_MINUTE in started[0].getMessage() and "chat-1" in started[0].getMessage()
    n = len(calls)
    clock.t += 20
    for _ in range(3):                                                              # still cooling: nothing is sent and nothing more is logged about the start
        with pytest.raises(ProviderUnavailable, match="cooling down"):
            call()
    assert len(calls) == n and len([r for r in caplog.records if "cooldown started" in r.getMessage()]) == 1
    clock.t += 10                                                                   # 30 s > 24 s: the model is called again, the end is logged once
    with pytest.raises(ProviderUnavailable):
        call()
    assert len(calls) > n and len([r for r in caplog.records if "cooldown ended" in r.getMessage()]) == 1


def test_a_per_day_quota_cools_down_until_the_daily_reset(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(oc, "next_daily_reset_seconds", lambda now=None: 5 * 3600.0)
    p = build(lambda req: httpx.Response(429, json=gemini_429(PER_DAY, "40s")), clock)         # even with a short retry delay: the day limit wins
    with pytest.raises(ProviderUnavailable):
        p._post("/chat/completions", json_body={"model": "chat-1", "messages": []})
    assert p._blocked_until["chat-1"] - clock.t == pytest.approx(5 * 3600.0)
    clock.t += 3600
    with pytest.raises(ProviderUnavailable, match="cooling down"):
        p._post("/chat/completions", json_body={"model": "chat-1", "messages": []})


def test_cooldown_seconds_rules_and_the_reset_fallback(monkeypatch):
    assert oc.cooldown_seconds({"quota_id": PER_MINUTE, "retry_delay_s": 23.0}) == 24.0
    assert oc.cooldown_seconds({"retry_delay_s": 0.5}) == 5.0 and oc.cooldown_seconds({}) == oc.QUOTA_COOLDOWN_S
    assert oc.cooldown_seconds({"retry_delay_s": 10 ** 9}) == oc.MAX_COOLDOWN_S
    assert 60.0 <= oc.cooldown_seconds({"quota_id": PER_DAY}) <= 24 * 3600 + 3600 or oc.cooldown_seconds({"quota_id": PER_DAY}) == oc.UNKNOWN_RESET_COOLDOWN_S
    import builtins
    real_import = builtins.__import__

    def no_zoneinfo(name, *a, **k):
        if name == "zoneinfo":
            raise ImportError("no tz database")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_zoneinfo)
    assert oc.next_daily_reset_seconds() == oc.UNKNOWN_RESET_COOLDOWN_S              # one hour when the time zone database is not installed
