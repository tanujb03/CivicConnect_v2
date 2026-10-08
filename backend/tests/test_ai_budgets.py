"""Per-model AI budgets (rpm / rpd / tpm), the Groq text fallback and the optional response cache. Fake clock, fake Redis, httpx mock transports: no network, no sleeping."""
import json
import logging

import httpx
import pytest

from ai.inference.errors import ProviderUnavailable
from ai.inference.provider import InputPart
from ai.inference.schemas import EvidenceInput
from backend.ai_gateway.providers import ChatCompletionsProvider, CompositeProvider, build_provider_from_env
from backend.ai_gateway.providers.budget import BudgetSpent, Limits, ModelBudgets, load_default_limits, parse_limits, quota_day
from backend.ai_gateway.providers.cache import ResponseCache, input_hash

SCHEMA = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"], "additionalProperties": False}


class Clock:
    def __init__(self, t=1_700_000_000.0):
        self.t, self.slept = t, []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


class FakeRedis:
    def __init__(self):
        self.data, self.ttl = {}, {}

    def get(self, k):
        return self.data.get(k)

    def set(self, k, v, ex=None):
        self.data[k], self.ttl[k] = v, ex

    def incr(self, k):
        self.data[k] = int(self.data.get(k, 0)) + 1
        return self.data[k]

    def expire(self, k, s):
        self.ttl[k] = s

    def pipeline(self):
        outer, ops = self, []

        class Pipe:
            def incr(self, k):
                ops.append(lambda: outer.incr(k))

            def expire(self, k, s):
                ops.append(lambda: outer.expire(k, s))

            def execute(self):
                return [op() for op in ops]
        return Pipe()


class DownRedis:
    def __getattr__(self, name):
        def boom(*a, **k):
            raise ConnectionError("redis down")
        return boom


def budgets(clock, limits, redis=None, **kw):
    return ModelBudgets(limits, provider="gemini", clock=clock, sleep=clock.sleep, redis_getter=lambda: redis, **kw)


# ---------------------------------------------------------------- the table and AI_MODEL_LIMITS
def test_default_table_has_the_quota_numbers_of_2026_10_08_and_env_overrides_them():
    d = load_default_limits()
    assert d["gemini-3.5-flash"] == Limits(5, 20, 250000) and d["gemini-3.5-flash-lite"] == Limits(15, 500, 250000)
    assert d["gemini-embedding-001"] == Limits(100, 1000, 30000) and d["whisper-large-v3"] == Limits(20, 2000, None)
    o = parse_limits("gemini-3.5-flash=10/40/-, new-model=1/-/5", d)
    assert o["gemini-3.5-flash"] == Limits(10, 40, None) and o["new-model"] == Limits(1, None, 5) and o["gemini-3.5-flash-lite"] == d["gemini-3.5-flash-lite"]
    assert parse_limits("off") == {} and parse_limits("", {}) == {}
    for bad in ("model", "model=a/b/c", "=1/2/3"):
        with pytest.raises(ValueError, match="AI_MODEL_LIMITS"):
            parse_limits(bad, {})


def test_no_default_selects_a_model_so_the_scarce_flash_model_is_only_reachable_by_explicit_env():
    assert build_provider_from_env({"GEMINI_API_KEY": "g", "GROQ_API_KEY": "q"}) is None              # keys alone configure no model
    p = build_provider_from_env({"GEMINI_API_KEY": "g", "AI_INTAKE_MODEL": "gemini-3.5-flash-lite", "AI_ANALYTICS_MODEL": "gemini-3.5-flash-lite"})
    assert {p.model_for(t) for t in ("intake", "triage", "analytics", "copilot")} == {"gemini-3.5-flash-lite"}
    src = " ".join(open(f, encoding="utf-8").read() for f in ("backend/ai_gateway/providers/factory.py", "backend/ai_gateway/providers/composite.py"))
    assert "gemini-3.5-flash" not in src                                                          # no route default names the scarce model


# ---------------------------------------------------------------- minute budgets
def test_rpm_waits_briefly_for_a_slot_and_refuses_a_long_wait():
    c = Clock()
    b = budgets(c, {"m": Limits(rpm=3)})
    b.acquire("m"); c.t += 1; b.acquire("m"); c.t += 1; b.acquire("m")
    with pytest.raises(BudgetSpent, match="per-minute budget of m is full"):
        b.acquire("m")                                                    # the next slot frees in 58 s > 8 s: refused, not queued
    assert c.slept == []
    c.t += 54                                                             # now the oldest request is 56 s old: a 4 s wait is acceptable
    b.acquire("m")
    assert len(c.slept) == 1 and 3.9 < c.slept[0] < 4.2


def test_tpm_counts_estimated_tokens_and_a_single_oversized_request_is_refused():
    c = Clock()
    b = budgets(c, {"e": Limits(tpm=1000)})
    b.acquire("e", 600)
    with pytest.raises(BudgetSpent, match="per-minute budget"):
        b.acquire("e", 600)                                               # 600 + 600 > 1000 and the first leaves the window in 60 s
    with pytest.raises(BudgetSpent, match="exceeds the 1000 tokens-per-minute"):
        b.acquire("e", 1200)
    c.t += 61
    b.acquire("e", 600)                                                   # the window slid


def test_models_without_a_limit_are_unrestricted():
    c = Clock()
    b = budgets(c, {"m": Limits(rpm=1)})
    for _ in range(50):
        b.acquire("other-model", 10 ** 6)
    assert c.slept == []


# ---------------------------------------------------------------- the daily budget
def test_a_spent_daily_budget_sends_nothing_and_is_logged_once(caplog):
    c, r = Clock(), FakeRedis()
    b = budgets(c, {"m": Limits(rpd=2)}, r)
    b.acquire("m"); b.acquire("m")
    caplog.set_level(logging.WARNING, logger="civicconnect.ai.budget")
    for _ in range(5):
        with pytest.raises(BudgetSpent, match="daily budget of m is spent"):
            b.acquire("m")
    assert len([x for x in caplog.records if "budget spent" in x.getMessage()]) == 1               # once, not per request
    assert b.used_today("m") == 2                                                                 # refused requests are not counted
    c.t += 24 * 3600                                                                              # the next quota day
    b.acquire("m")
    assert b.used_today("m") == 1 and quota_day(c.t, "America/Los_Angeles") != quota_day(c.t - 24 * 3600, "America/Los_Angeles")


def test_the_daily_counter_is_shared_through_redis_and_expires():
    c, r = Clock(), FakeRedis()
    a, b = budgets(c, {"m": Limits(rpd=3)}, r), budgets(c, {"m": Limits(rpd=3)}, r)               # two processes
    a.acquire("m"); b.acquire("m"); a.acquire("m")
    with pytest.raises(BudgetSpent):
        b.acquire("m")
    key = next(iter(r.data))
    assert key.startswith("civic:aibudget:rpd:gemini:m:") and r.ttl[key] == 26 * 3600


def test_with_redis_down_the_daily_counter_falls_back_to_the_process(caplog):
    c = Clock()
    b = budgets(c, {"m": Limits(rpd=2)}, DownRedis())
    b.acquire("m"); b.acquire("m")
    with pytest.raises(BudgetSpent):
        b.acquire("m")


# ---------------------------------------------------------------- inside the provider
def chat_ok(model):
    return {"model": model, "choices": [{"message": {"content": json.dumps({"a": "x"})}, "finish_reason": "stop"}]}


def provider(handler, models, name="gemini", **kw):
    return ChatCompletionsProvider(name, f"https://{name}.test/v1", "SECRET-KEY-123", models, client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None, **kw)


def call(p, task="intake", text="hello"):
    return p.structured_completion(task=task, instructions="i", parts=[InputPart.of_text(text)], schema_name="s", json_schema=SCHEMA)


def test_the_provider_does_not_send_when_the_daily_budget_is_spent():
    c, sent = Clock(), []
    p = provider(lambda req: (sent.append(1), httpx.Response(200, json=chat_ok("m")))[1], {"intake": "m"}, budgets=budgets(c, {"m": Limits(rpd=1)}, FakeRedis()))
    assert call(p).data == {"a": "x"}
    with pytest.raises(BudgetSpent) as e:
        call(p)
    assert len(sent) == 1 and e.value.status_code == 429 and isinstance(e.value, ProviderUnavailable)


# ---------------------------------------------------------------- Groq as the text fallback
class Img:
    pass


def test_a_text_call_falls_back_to_groq_when_the_primary_is_out_of_budget_but_images_do_not():
    c, sent = Clock(), {"g": 0, "q": 0}

    def gem(req):
        sent["g"] += 1
        return httpx.Response(200, json=chat_ok("gem"))

    def groq(req):
        sent["q"] += 1
        return httpx.Response(200, json=chat_ok("groq-text-model"))

    primary = provider(gem, {"intake": "gem"}, budgets=budgets(c, {"gem": Limits(rpd=1)}, FakeRedis()))
    fb = provider(groq, {"intake": "groq-text-model"}, name="groq")
    comp = CompositeProvider({"intake": primary}, {"intake": fb})
    assert call(comp).model == "gem" and sent == {"g": 1, "q": 0}
    r = call(comp)                                                          # budget spent: Groq answers
    assert r.model == "groq-text-model" and sent == {"g": 1, "q": 1}
    image = EvidenceInput(evidence_id="e", media_type="IMAGE", mime_type="image/jpeg", data=b"\xff\xd8\xff")
    with pytest.raises(BudgetSpent):                                         # an image cannot go to a text model: it degrades in the gateway
        comp.structured_completion(task="intake", instructions="i", parts=[InputPart.of_image(image)], schema_name="s", json_schema=SCHEMA)
    assert sent["q"] == 1


def test_factory_builds_the_groq_fallback_only_with_a_key_and_an_explicit_model():
    env = {"GEMINI_API_KEY": "g", "GROQ_API_KEY": "q", "AI_INTAKE_MODEL": "gem", "AI_ANALYTICS_MODEL": "gem", "AI_TRANSCRIPTION_MODEL": "whisper"}
    assert build_provider_from_env(env).fallbacks == {}
    p = build_provider_from_env({**env, "AI_FALLBACK_TEXT_MODEL": "groq-text"})
    assert set(p.fallbacks) == {"intake", "triage", "resolution", "analytics", "copilot"} & set(p.routes) and p.fallbacks["intake"].model_for("intake") == "groq-text"
    assert build_provider_from_env({**{k: v for k, v in env.items() if k != "GROQ_API_KEY"}, "AI_FALLBACK_TEXT_MODEL": "groq-text"}).fallbacks == {}


# ---------------------------------------------------------------- the response cache
def cached(handler, r, models=None, fallbacks=None):
    return CompositeProvider({"intake": provider(handler, models or {"intake": "m"})}, fallbacks, ResponseCache(ttl_s=3600, redis_getter=lambda: r))


def test_a_repeated_call_is_answered_from_the_cache_with_a_ttl():
    r, n = FakeRedis(), {"c": 0}

    def h(req):
        n["c"] += 1
        return httpx.Response(200, json=chat_ok("m"))

    comp = cached(h, r)
    a, b = call(comp, text="one"), call(comp, text="one")
    assert a == b and n["c"] == 1
    call(comp, text="two")
    assert n["c"] == 2                                                                  # another input is a miss
    assert all(ttl == 3600 for ttl in r.ttl.values()) and any(k.startswith("civic:aicache:structured:intake:m:") for k in r.data)


def test_the_cache_key_includes_the_model_and_hashes_image_bytes_not_stores_them():
    r = FakeRedis()
    comp = cached(lambda req: httpx.Response(200, json=chat_ok("m")), r)
    call(comp)
    other = cached(lambda req: httpx.Response(200, json=chat_ok("m2")), r, {"intake": "m2"})
    call(other)
    assert len(r.data) == 2
    e1 = EvidenceInput(evidence_id="e", media_type="IMAGE", data=b"A" * 10)
    e2 = EvidenceInput(evidence_id="e", media_type="IMAGE", data=b"B" * 10)
    assert input_hash(p=[InputPart.of_image(e1)]) != input_hash(p=[InputPart.of_image(e2)])
    assert "AAAAAAAAAA" not in " ".join(map(str, r.data.values())) and "AAAAAAAAAA" not in " ".join(r.data)


def test_errors_and_fallback_answers_are_never_cached():
    r = FakeRedis()
    comp = cached(lambda req: httpx.Response(500, text="down"), r)
    with pytest.raises(ProviderUnavailable):
        call(comp)
    assert not r.data
    fb = provider(lambda req: httpx.Response(200, json=chat_ok("groq")), {"intake": "groq"}, name="groq")
    comp2 = cached(lambda req: httpx.Response(429, json={"error": {"message": "quota"}}), r, fallbacks={"intake": fb})
    assert call(comp2).model == "groq" and not r.data


def test_the_cache_is_off_by_default_and_without_redis_calls_pass_through():
    assert ResponseCache.from_env({}) is None and ResponseCache.from_env({"AI_CACHE_ENABLED": "false"}) is None
    assert ResponseCache.from_env({"AI_CACHE_ENABLED": "true", "AI_CACHE_TTL_S": "60"}).ttl_s == 60
    assert build_provider_from_env({"GEMINI_API_KEY": "g", "AI_INTAKE_MODEL": "m"}).cache is None
    n = {"c": 0}

    def h(req):
        n["c"] += 1
        return httpx.Response(200, json=chat_ok("m"))

    comp = CompositeProvider({"intake": provider(h, {"intake": "m"})}, None, ResponseCache(redis_getter=lambda: None))
    call(comp); call(comp)
    assert n["c"] == 2
    broken = CompositeProvider({"intake": provider(h, {"intake": "m"})}, None, ResponseCache(redis_getter=lambda: DownRedis()))
    assert call(broken).data == {"a": "x"}                                             # a broken cache never fails an AI call
