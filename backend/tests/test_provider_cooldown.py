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
