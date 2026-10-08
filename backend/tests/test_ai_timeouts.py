"""Provider deadline (AI_PROVIDER_TIMEOUT_S) and the provider-vs-waited timing: fake clock, httpx mock transports, no network, nothing really sleeps.

A "hung" server is emulated like httpx does it: the request carries its read timeout (``req.extensions["timeout"]``), the fake clock advances by min(hang, that timeout) and a
``ReadTimeout`` is raised when the timeout ended the wait. So the timeout the adapter passes decides how long the (fake) call lasts."""
from __future__ import annotations

import json
import logging

import httpx
import pytest

from ai.inference.errors import ProviderUnavailable
from ai.inference.provider import InputPart
from ai.inference.schemas import EvidenceInput
from backend.ai_gateway import localization, timing
from backend.ai_gateway.providers import ChatCompletionsProvider, CompositeProvider
from backend.ai_gateway.providers.budget import BudgetSpent, Limits, ModelBudgets
from backend.ai_gateway.providers.factory import build_backends_from_env, provider_deadline_s
from backend.ai_gateway.providers.openai_compat import DEFAULT_DEADLINE_S, ProviderTimeout
from backend.tests.ai_helpers import install
from backend.tests.helpers import create_case

SCHEMA = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"], "additionalProperties": False}
PROMPT = "PROMPT-TEXT-OF-THE-CITIZEN"
INTAKE_EN = {"title": "Pothole near the school", "description": "A deep pothole near the school gate", "category": "roads", "subcategory": "pothole", "severity": "HIGH",
             "language": "en", "transcript": None, "confidence": 0.9, "reasons": ["pothole"], "image_observations": []}
INTAKE_HI = {**INTAKE_EN, "language": "hi"}
LOCAL = {"title": "स्कूल के पास गड्ढा", "summary": "स्कूल के गेट के पास गहरा गड्ढा है।"}
T0 = 1000.0


class Clock:
    def __init__(self, t=T0):
        self.t, self.slept = t, []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


def chat(content):
    return {"model": "served", "choices": [{"message": {"content": json.dumps(content)}, "finish_reason": "stop"}]}


def build(handler, clock, name="gemini", models=None, **kw):
    return ChatCompletionsProvider(name, f"https://{name}.test/v1", "SECRET-KEY-123", models or {"intake": f"{name}-model", "embedding": "emb-1"},
                                   client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=clock.sleep, clock=clock, **kw)


def call(p, task="intake", text=PROMPT, parts=None):
    return p.structured_completion(task=task, instructions="i", parts=parts or [InputPart.of_text(text)], schema_name="s", json_schema=SCHEMA)


def hang(clock, seconds=25.0, then=None, seen=None):
    """A server that takes ``seconds`` to answer (or never does when ``then`` is None); the client's read timeout cuts the wait short."""
    def handler(req):
        limit = req.extensions["timeout"]["read"]
        if seen is not None:
            seen.append(limit)
        if seconds > limit or then is None:
            clock.t += min(seconds, limit)
            raise httpx.ReadTimeout("timed out", request=req)
        clock.t += seconds
        return then(req)
    return handler


def ok(content=None):
    return lambda req: httpx.Response(200, json=chat(content or {"a": "x"}))


# ---------------------------------------------------------------- the deadline inside one provider call
def test_a_slow_provider_raises_at_the_deadline_not_at_the_45_second_attempt_timeout():
    c, seen = Clock(), []
    p = build(hang(c, 25.0, seen=seen), c, timeout_s=45.0, max_retries=2)               # default deadline: 20 s
    with pytest.raises(ProviderTimeout, match=r"gemini: deadline of 20 s exceeded") as e:
        call(p)
    assert c.t - T0 == pytest.approx(20.0) and seen == [pytest.approx(20.0)]             # one attempt, cut at 20 s, no retry
    assert e.value.timed_out is True and e.value.status_code is None and isinstance(e.value, ProviderUnavailable)
    assert "SECRET-KEY-123" not in str(e.value)


def test_a_call_that_would_answer_after_the_deadline_is_cut_too():
    c = Clock()
    p = build(hang(c, 25.0, then=ok()), c, timeout_s=60.0, max_retries=0, deadline_s=20.0)
    with pytest.raises(ProviderTimeout):
        call(p)
    assert c.t - T0 == pytest.approx(20.0)


def test_retries_never_extend_past_the_deadline_and_each_attempt_gets_min_of_timeout_and_time_left():
    c, seen = Clock(), []
    p = build(hang(c, 25.0, seen=seen), c, timeout_s=8.0, max_retries=2)
    with pytest.raises(ProviderTimeout, match="deadline of 20 s exceeded"):
        call(p)
    assert seen == [pytest.approx(8.0), pytest.approx(8.0), pytest.approx(2.5)]          # 8 + 0.5 + 8 + 1 leaves 2.5 s for the third attempt
    assert c.slept == [0.5, 1.0] and c.t - T0 == pytest.approx(20.0)


def test_a_retry_sleep_that_does_not_fit_is_not_taken_and_the_call_stops():
    c, sent = Clock(), []

    def handler(req):
        sent.append(1)
        c.t += 1.0
        return httpx.Response(503, headers={"retry-after": "8"}, text="busy")

    p = build(handler, c, deadline_s=5.0, max_retries=2)
    with pytest.raises(ProviderTimeout, match=r"deadline of 5 s exceeded .*HTTP 503"):
        call(p)
    assert len(sent) == 1 and c.slept == [] and c.t - T0 == pytest.approx(1.0)


def test_the_per_attempt_timeout_still_applies_when_it_is_the_smaller_one():
    c, seen = Clock(), []
    p = build(hang(c, 25.0, then=ok(), seen=seen), c, timeout_s=3.0, max_retries=0)
    with pytest.raises(ProviderUnavailable, match="transport error ReadTimeout") as e:
        call(p)
    assert seen == [3.0] and getattr(e.value, "timed_out", False) and not isinstance(e.value, ProviderTimeout) and c.t - T0 == pytest.approx(3.0)


def test_without_a_deadline_the_client_timeout_is_passed_unchanged():
    c, seen = Clock(), []
    p = build(hang(c, 1.0, then=ok(), seen=seen), c, timeout_s=45.0, deadline_s=None)
    assert call(p).data == {"a": "x"} and seen == [45.0]


def test_a_rate_limit_spacing_that_does_not_fit_stops_the_call_before_sending():
    c, sent = Clock(), []

    def handler(req):
        sent.append(1)
        return httpx.Response(200, json=chat({"a": "x"}))

    p = build(handler, c, rpm=1.0, deadline_s=20.0)                                       # one request a minute: the next one must wait 60 s
    assert call(p).data == {"a": "x"}
    with pytest.raises(ProviderTimeout, match=r"rate-limit spacing"):
        call(p)
    assert len(sent) == 1 and c.slept == []


def test_a_budget_wait_that_used_up_the_deadline_stops_before_sending():
    c, sent = Clock(), []
    b = ModelBudgets({"gemini-model": Limits(rpm=1)}, provider="gemini", clock=c, sleep=c.sleep, redis_getter=lambda: None, max_wait_s=8.0)
    p = build(lambda req: (sent.append(1), httpx.Response(200, json=chat({"a": "x"})))[1], c, deadline_s=5.0, budgets=b)
    assert call(p).data == {"a": "x"}
    c.t += 54.0                                                                           # the minute window frees up in 6 s: within the budget limit (8 s), past the deadline (5 s)
    with pytest.raises(ProviderTimeout, match="no time left for attempt 1"):
        call(p)
    assert len(sent) == 1


def test_a_timeout_starts_no_cooldown_and_the_next_call_is_sent():
    c, sent = Clock(), []
    mode = {"slow": True}

    def handler(req):
        sent.append(1)
        return hang(c, 25.0, then=ok())(req) if mode["slow"] else httpx.Response(200, json=chat({"a": "x"}))

    p = build(handler, c)
    with pytest.raises(ProviderTimeout):
        call(p)
    assert p._blocked_until == {} and p._cooling == set()
    mode["slow"] = False
    assert call(p).data == {"a": "x"} and len(sent) == 2                                  # not "cooling down": it was called again at once


def test_a_429_found_when_the_deadline_stops_the_retries_still_starts_the_quota_cooldown():
    c = Clock()

    def handler(req):
        c.t += 1.0
        return httpx.Response(429, headers={"retry-after": "8"}, json={"error": {"message": "quota"}})

    p = build(handler, c, deadline_s=3.0)
    with pytest.raises(ProviderUnavailable, match="HTTP 429") as e:
        call(p)
    assert e.value.status_code == 429 and not isinstance(e.value, ProviderTimeout) and "gemini-model" in p._blocked_until


# ---------------------------------------------------------------- the timing log line and the accumulator
def test_the_log_line_separates_provider_time_from_waited_time_and_holds_no_prompt_or_key(caplog):
    c, n = Clock(), {"i": 0}

    def handler(req):
        n["i"] += 1
        if n["i"] == 1:
            c.t += 3.0
            return httpx.Response(503, text="busy")
        c.t += 2.0
        return httpx.Response(200, json=chat({"a": "x"}))

    p = build(handler, c)
    caplog.set_level(logging.INFO, logger="civicconnect.ai.compat")
    timing.start()
    call(p)
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("ai provider call")]
    assert len(lines) == 1
    line = lines[0]
    for part in ("task=intake", "backend=gemini", "model=gemini-model", "attempts=2", "provider_ms=5000", "waited_ms=500", "total_ms=5500", "outcome=ok"):
        assert part in line, line
    assert PROMPT not in caplog.text and "SECRET-KEY-123" not in caplog.text
    assert timing.snapshot() == {"provider_ms": 5000, "waited_ms": 500, "provider_calls": 1}


def test_budget_waits_count_as_waited_not_provider_time(caplog):
    c = Clock()
    b = ModelBudgets({"gemini-model": Limits(rpm=1)}, provider="gemini", clock=c, sleep=c.sleep, redis_getter=lambda: None, max_wait_s=8.0)
    p = build(lambda req: (setattr(c, "t", c.t + 1.0), httpx.Response(200, json=chat({"a": "x"})))[1], c, budgets=b)
    call(p)
    c.t += 56.0                                                                           # the next slot opens in about 3 s: the budget waits for it
    caplog.set_level(logging.INFO, logger="civicconnect.ai.compat")
    timing.start()
    call(p)
    snap = timing.snapshot()
    assert snap["provider_ms"] == 1000 and 2900 <= snap["waited_ms"] <= 3200 and "outcome=ok" in caplog.text


@pytest.mark.parametrize("handler_status,outcome", [(400, "http_400"), (503, "http_503")])
def test_the_outcome_names_the_http_status(caplog, handler_status, outcome):
    c = Clock()
    p = build(lambda req: httpx.Response(handler_status, text="no"), c, max_retries=1)
    caplog.set_level(logging.INFO, logger="civicconnect.ai.compat")
    with pytest.raises(ProviderUnavailable):
        call(p)
    assert f"outcome={outcome}" in caplog.text


def test_the_outcome_is_timeout_for_a_deadline_and_budget_when_nothing_was_sent(caplog):
    c = Clock()
    caplog.set_level(logging.INFO, logger="civicconnect.ai.compat")
    with pytest.raises(ProviderTimeout):
        call(build(hang(c, 25.0), c))
    assert "outcome=timeout" in caplog.text and "attempts=1" in caplog.text
    caplog.clear()
    b = ModelBudgets({"gemini-model": Limits(rpd=1)}, provider="gemini", clock=c, sleep=c.sleep, redis_getter=lambda: None)
    p = build(ok(), c, budgets=b)
    call(p)
    with pytest.raises(BudgetSpent):
        call(p)
    assert "outcome=budget" in caplog.text and "attempts=0" in caplog.text


def test_the_accumulator_is_per_context_and_a_noop_before_start():
    timing.add(5, 5)                                         # without start() nothing is recorded and nothing fails
    timing.start()
    timing.add(10.9, 2.2)
    timing.add(1, 0, calls=2)
    assert timing.snapshot() == {"provider_ms": 11, "waited_ms": 2, "provider_calls": 3}
    timing.start()                                           # a new request restarts it
    assert timing.snapshot() == {"provider_ms": 0, "waited_ms": 0, "provider_calls": 0}


# ---------------------------------------------------------------- the fallback after a timeout
def test_a_timeout_goes_to_the_groq_fallback_with_its_own_fresh_deadline(caplog):
    c, seen_g, seen_q = Clock(), [], []
    gem = build(hang(c, 25.0, seen=seen_g), c)
    groq = build(hang(c, 2.0, then=ok(), seen=seen_q), c, name="groq")
    comp = CompositeProvider({"intake": gem}, {"intake": groq})
    caplog.set_level(logging.INFO)
    timing.start()
    r = call(comp)
    assert r.data == {"a": "x"} and seen_g == [pytest.approx(20.0)] and seen_q == [pytest.approx(20.0)]      # Groq got the full 20 s, not what was left
    assert timing.snapshot()["provider_calls"] == 2 and timing.snapshot()["provider_ms"] == 22000
    assert "timed out" in caplog.text and "fresh deadline" in caplog.text
    assert gem._blocked_until == {}                                                                          # no cooldown for a timeout


def test_an_image_call_has_no_text_fallback_so_the_timeout_propagates(caplog):
    c = Clock()
    comp = CompositeProvider({"intake": build(hang(c, 25.0), c)}, {"intake": build(ok(), c, name="groq")})
    image = EvidenceInput(evidence_id="e", media_type="IMAGE", mime_type="image/jpeg", data=b"\xff\xd8\xff")
    caplog.set_level(logging.INFO)
    with pytest.raises(ProviderTimeout):
        call(comp, parts=[InputPart.of_image(image)])
    assert "request degrades" in caplog.text and c.t - T0 == pytest.approx(20.0)


# ---------------------------------------------------------------- AI_PROVIDER_TIMEOUT_S
@pytest.mark.parametrize("raw,expected", [(None, 20.0), ("", 20.0), ("   ", 20.0), ("0", 20.0), ("0.0", 20.0), ("20", 20.0), ("35", 35.0), ("7.5", 7.5)])
def test_the_deadline_setting_defaults_to_20_seconds(raw, expected):
    assert provider_deadline_s({} if raw is None else {"AI_PROVIDER_TIMEOUT_S": raw}) == expected and DEFAULT_DEADLINE_S == 20.0


@pytest.mark.parametrize("raw", ["abc", "-5", "nan", "inf", "20s"])
def test_a_garbage_deadline_is_a_clear_configuration_error(raw):
    with pytest.raises(ValueError, match="AI_PROVIDER_TIMEOUT_S"):
        provider_deadline_s({"AI_PROVIDER_TIMEOUT_S": raw})


def test_the_factory_gives_every_backend_the_deadline_and_keeps_the_attempt_timeout():
    env = {"GEMINI_API_KEY": "g", "GROQ_API_KEY": "q", "AI_INTAKE_MODEL": "gem", "AI_PROVIDER_TIMEOUT_S": "35", "AI_REQUEST_TIMEOUT_S": "30"}
    backends = build_backends_from_env(env)
    assert {b._deadline_s for b in backends.values()} == {35.0} and {b._timeout_s for b in backends.values()} == {30.0}
    assert {b._deadline_s for b in build_backends_from_env({k: v for k, v in env.items() if k != "AI_PROVIDER_TIMEOUT_S"}).values()} == {20.0}


# ---------------------------------------------------------------- through the real endpoints (SQL-backed gateway)
def two_backends(clock, gem_handler, groq_handler=None):
    gem = build(gem_handler, clock)
    return CompositeProvider({"intake": gem}, {"intake": build(groq_handler, clock, name="groq")} if groq_handler else {})


def post_intake(e, language="en", text="pothole near the school gate", who="alice"):
    r = e.client.post("/api/v1/cases/intake/analyze", headers=e.headers(who), json={"text": text, "language_hint": language})
    assert r.status_code == 200, r.text
    return r.json()


def assert_timing(meta, *, calls=None):
    t = meta["timing"]
    assert set(t) == {"provider_ms", "waited_ms", "total_ms", "provider_calls", "request_deadline_s"} and all(isinstance(v, (int, float)) and v >= 0 for v in t.values()), t
    if calls is not None:
        assert t["provider_calls"] == calls
    return t


def test_intake_triage_copilot_and_explain_carry_ai_metadata_timing(staffed):
    from ai.inference.providers.fake import FakeProvider
    e = staffed
    install(FakeProvider(structured={"intake": INTAKE_EN}))
    assert_timing(post_intake(e)["ai_metadata"], calls=0)                                 # a fake provider makes no HTTP call: zeros, but the block is there
    case = create_case(e, "alice")
    r = e.client.post(f"/api/v1/cases/{case['id']}/triage/analyze", headers=e.headers("admin"))
    assert r.status_code == 200, r.text
    assert_timing(r.json()["ai_metadata"], calls=0)
    r = e.client.post("/api/v1/copilot/query", headers=e.headers("admin"), json={"query": "how many cases are open?"})
    assert r.status_code == 200, r.text
    assert_timing(r.json()["ai_metadata"])
    r = e.client.post("/api/v1/analytics/explain", headers=e.headers("admin"), json={})
    assert r.status_code == 200, r.text
    assert_timing(r.json()["ai_metadata"])


def test_a_real_http_provider_call_shows_up_in_the_response_timing(staffed):
    e, c = staffed, Clock()
    install(two_backends(c, hang(c, 3.0, then=ok(INTAKE_EN))))
    t = assert_timing(post_intake(e)["ai_metadata"], calls=1)
    assert t["provider_ms"] == 3000 and t["waited_ms"] == 0


def test_a_degraded_intake_without_a_provider_still_reports_timing(staffed):
    body = post_intake(staffed)
    assert body["ai_metadata"]["degraded"] is True
    assert_timing(body["ai_metadata"], calls=0)


def test_a_hung_provider_without_a_fallback_degrades_to_the_rules_answer_within_the_deadline(staffed, caplog):
    e, c = staffed, Clock()
    install(two_backends(c, hang(c, 25.0)))
    caplog.set_level(logging.INFO)
    body = post_intake(e)
    assert any(w.startswith("PROVIDER_UNAVAILABLE") for w in body["warnings"]) and body["ai_metadata"]["degraded"] is True
    assert body["ai_metadata"]["source"] != "provider"
    t = assert_timing(body["ai_metadata"], calls=1)
    assert t["provider_ms"] == 20000 and c.t - T0 == pytest.approx(20.0)                  # cut at the deadline, not 45 s
    assert "outcome=timeout" in caplog.text


def test_a_hung_provider_with_a_groq_fallback_is_answered_by_the_fallback(staffed):
    e, c = staffed, Clock()
    install(two_backends(c, hang(c, 25.0), hang(c, 1.5, then=ok(INTAKE_EN))))
    body = post_intake(e)
    assert not any(w.startswith("PROVIDER_UNAVAILABLE") for w in body["warnings"]) and body["ai_metadata"]["source"] == "provider"
    assert body["proposal"]["category"] == "roads"
    t = assert_timing(body["ai_metadata"], calls=2)
    assert t["provider_ms"] == 21500


def test_a_hung_localization_call_is_bounded_and_costs_only_the_local_title(staffed, caplog):
    e, c = staffed, Clock()

    def handler(req):
        schema = json.loads(req.content)["response_format"]["json_schema"]["name"]
        return hang(c, 25.0)(req) if schema == localization.SCHEMA_NAME else httpx.Response(200, json=chat(INTAKE_HI))

    install(two_backends(c, handler))
    body = post_intake(e, language="hi", text="school ke paas gaddha hai")
    assert body["proposal"]["category"] == "roads" and not body["proposal"].get("title_local")
    assert any(w.startswith(localization.WARNING) for w in body["warnings"]) and not any(w.startswith("PROVIDER_UNAVAILABLE") for w in body["warnings"])
    t = assert_timing(body["ai_metadata"], calls=2)
    assert t["provider_ms"] >= 20000 and c.t - T0 == pytest.approx(20.0)                  # the localisation time counts in provider_ms, capped at the deadline


# ---------------------------------------------------------------- the request-level cap (AI_REQUEST_DEADLINE_S)
@pytest.fixture(autouse=True)
def _fresh_request_context():
    timing._acc.set(None)                                      # the accumulator lives in a ContextVar: never leak a request deadline from one test into the next
    yield
    timing._acc.set(None)


@pytest.mark.parametrize("raw,expected", [(None, 30.0), ("", 30.0), (" ", 30.0), ("0", 30.0), ("30", 30.0), ("12", 12.0), ("45.5", 45.5)])
def test_the_request_deadline_setting_defaults_to_30_seconds(raw, expected):
    assert timing.request_deadline_s({} if raw is None else {"AI_REQUEST_DEADLINE_S": raw}) == expected and timing.DEFAULT_REQUEST_DEADLINE_S == 30.0


@pytest.mark.parametrize("raw", ["abc", "-1", "nan", "inf", "30s"])
def test_a_garbage_request_deadline_is_a_clear_error_at_provider_build_time(raw):
    with pytest.raises(ValueError, match="AI_REQUEST_DEADLINE_S"):
        timing.request_deadline_s({"AI_REQUEST_DEADLINE_S": raw})
    with pytest.raises(ValueError, match="AI_REQUEST_DEADLINE_S"):
        build_backends_from_env({"GEMINI_API_KEY": "g", "AI_INTAKE_MODEL": "m", "AI_REQUEST_DEADLINE_S": raw})


def test_the_request_budget_counts_provider_plus_waited_time_and_is_spent_when_less_than_a_useful_call_is_left(caplog):
    assert timing.remaining() is None and timing.spent() is False and timing.deadline_s() is None
    timing.start(None)
    timing.add(100000, 0)
    assert timing.remaining() is None and not timing.spent()                              # no request deadline: never spent
    caplog.set_level(logging.WARNING, logger="civicconnect.ai.timing")
    timing.start(30.0)
    timing.add(20000, 3000)
    assert timing.remaining() == pytest.approx(7.0) and not timing.spent() and timing.deadline_s() == 30.0
    timing.add(1500, 0)
    assert timing.spent() and timing.spent()                                              # 5.5 s left is below the 6 s a call needs
    assert caplog.text.count("ai request deadline reached") == 1                         # logged once per request
    timing.start(30.0)                                                                    # a new request starts fresh (and may log again)
    assert timing.remaining() == 30.0 and not timing.spent()
    timing.start(10.0)
    timing.add(7000, 0)
    assert not timing.spent()                                                             # for a short deadline a call needs only a fifth of it (2 s)


def test_gemini_timeout_then_groq_timeout_cannot_exceed_the_request_deadline(caplog):
    c, seen_g, seen_q = Clock(), [], []
    comp = CompositeProvider({"intake": build(hang(c, 25.0, seen=seen_g), c)}, {"intake": build(hang(c, 25.0, seen=seen_q), c, name="groq")})
    caplog.set_level(logging.INFO)
    timing.start(30.0)
    with pytest.raises(ProviderTimeout, match=r"groq: deadline of 10 s exceeded"):
        call(comp)
    assert seen_g == [pytest.approx(20.0)] and seen_q == [pytest.approx(10.0)]            # Groq got only what the request had left
    assert c.t - T0 == pytest.approx(30.0) and timing.snapshot()["provider_calls"] == 2
    assert caplog.text.count("ai request deadline reached") == 1


def test_a_fallback_is_skipped_when_the_primary_used_up_the_request_budget(caplog):
    c, seen_q = Clock(), []
    comp = CompositeProvider({"intake": build(hang(c, 30.0), c, deadline_s=26.0)}, {"intake": build(hang(c, 1.0, then=ok(), seen=seen_q), c, name="groq")})
    caplog.set_level(logging.INFO)
    timing.start(30.0)
    with pytest.raises(ProviderTimeout):
        call(comp)                                                                        # the call hangs until its 26 s deadline: 4 s left, below the 6 s a call needs
    assert seen_q == [] and "fallback groq is skipped" in caplog.text


def test_a_call_after_the_budget_is_spent_is_not_sent(caplog):
    c, sent = Clock(), []
    p = build(lambda req: (sent.append(1), httpx.Response(200, json=chat({"a": "x"})))[1], c)
    caplog.set_level(logging.INFO)
    timing.start(30.0)
    timing.add(26000, 0)
    with pytest.raises(ProviderTimeout, match="request deadline of 30 s reached"):
        call(p)
    assert sent == [] and "outcome=request_deadline" in caplog.text


def test_each_call_deadline_is_min_of_the_provider_deadline_and_what_the_request_has_left():
    c, seen = Clock(), []
    p = build(hang(c, 1.0, then=ok(), seen=seen), c, deadline_s=20.0)
    timing.start(30.0)
    timing.add(18000, 0)
    call(p)
    assert seen == [pytest.approx(12.0)]
    timing.start(30.0)
    call(p)
    assert seen[-1] == pytest.approx(20.0)


def test_a_hindi_intake_whose_main_call_used_25_seconds_skips_localization(staffed):
    e, c, schemas = staffed, Clock(), []

    def handler(req):
        schemas.append(json.loads(req.content)["response_format"]["json_schema"]["name"])
        return hang(c, 25.0, then=lambda r: httpx.Response(200, json=chat(INTAKE_HI)))(req)

    install(CompositeProvider({"intake": build(handler, c, deadline_s=40.0)}))
    body = post_intake(e, language="hi", text="school ke paas gaddha hai")
    assert localization.SCHEMA_NAME not in schemas and len(schemas) == 1                  # the localisation call was never sent
    assert body["ai_metadata"]["source"] == "provider" and not body["proposal"].get("title_local")
    assert any(w.startswith(localization.WARNING) for w in body["warnings"]) and not any(w.startswith("PROVIDER_UNAVAILABLE") for w in body["warnings"])
    t = assert_timing(body["ai_metadata"], calls=1)
    assert t["provider_ms"] == 25000 and t["request_deadline_s"] == 30.0


def test_two_hung_backends_degrade_the_request_within_the_request_deadline_and_the_next_request_starts_fresh(staffed):
    e, c = staffed, Clock()
    mode = {"hung": True}

    def answer(req):
        return hang(c, 25.0)(req) if mode["hung"] else httpx.Response(200, json=chat(INTAKE_EN))

    install(two_backends(c, answer, answer))
    body = post_intake(e)
    assert any(w.startswith("PROVIDER_UNAVAILABLE") for w in body["warnings"]) and body["ai_metadata"]["degraded"] is True
    assert c.t - T0 == pytest.approx(30.0)                                                # 20 s Gemini + 10 s Groq, not 40 s
    assert assert_timing(body["ai_metadata"], calls=2)["request_deadline_s"] == 30.0
    mode["hung"] = False
    again = post_intake(e)                                                                # the budget is per request: this one calls the provider normally
    assert again["ai_metadata"]["source"] == "provider"
    assert assert_timing(again["ai_metadata"], calls=1)["provider_calls"] == 1


def test_the_gateway_reads_the_request_deadline_from_the_environment_and_survives_garbage(staffed, monkeypatch):
    from ai.inference.providers.fake import FakeProvider
    e = staffed
    install(FakeProvider(structured={"intake": INTAKE_EN}))
    monkeypatch.setenv("AI_REQUEST_DEADLINE_S", "12")
    assert post_intake(e)["ai_metadata"]["timing"]["request_deadline_s"] == 12.0
    monkeypatch.setenv("AI_REQUEST_DEADLINE_S", "garbage")
    assert post_intake(e)["ai_metadata"]["timing"]["request_deadline_s"] == 30.0
    monkeypatch.delenv("AI_REQUEST_DEADLINE_S")
    assert post_intake(e)["ai_metadata"]["timing"]["request_deadline_s"] == 30.0
