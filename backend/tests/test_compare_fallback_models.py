"""scripts/dev/compare_fallback_models.py: row picking, token window, summaries and the run loop over the REAL adapter on httpx mock transports (no network, no keys)."""
import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.ai_gateway.providers import ChatCompletionsProvider  # noqa: E402

_spec = importlib.util.spec_from_file_location("compare_fallback_models", ROOT / "scripts" / "dev" / "compare_fallback_models.py")
cmp = importlib.util.module_from_spec(_spec)
sys.modules["compare_fallback_models"] = cmp
_spec.loader.exec_module(cmp)


def gold_rows():
    out = []
    for lang in ("en", "hi", "mr", "hi-Latn"):
        for i in range(4):
            out.append({"text": f"{lang} complaint number {i} " + "x" * 120, "label_id": "roads/pothole" if i % 2 else "water_supply/pipe_leakage", "language": lang})
    return out


def answer(category="roads", sub="pothole", **over):
    data = {"title": "t", "description": "d", "category": category, "subcategory": sub, "severity": "MEDIUM", "language": "hi", "confidence": 0.8, "reasons": []}
    data.update(over)
    return data


def chat(data, usage=(900, 100)):
    return {"model": "m", "choices": [{"message": {"content": json.dumps(data)}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": usage[0], "completion_tokens": usage[1], "total_tokens": usage[0] + usage[1]}}


def factory(handler, mode="json_schema"):
    def make(model):
        return ChatCompletionsProvider("groq", "https://api.example.test/v1", "SECRET-KEY-123", {"intake": model}, max_retries=0, structured_mode=mode, deadline_s=60,
                                       sleep=lambda s: None, client=httpx.Client(transport=httpx.MockTransport(handler)))
    return make


def run(rows, handler, **kw):
    slept = []
    calls = cmp.run_model("model-a", rows, factory(handler, kw.pop("mode", "json_schema")), window=kw.pop("window", cmp.TokenWindow(7000)), sleep=slept.append, log=lambda s: None)
    return calls, slept


# ------------------------------------------------------------------------------------------ pure logic
def test_pick_rows_fixed_rule_is_deterministic_and_balanced():
    rows = gold_rows()
    a, b = cmp.pick_rows(rows), cmp.pick_rows(list(reversed(rows)))
    assert [r["id"] for r in a] == [r["id"] for r in b]
    assert [r["language"] for r in a] == ["hi", "hi", "mr", "mr", "hi-Latn", "hi-Latn"]
    for lang in ("hi", "mr", "hi-Latn"):
        mine = sorted(cmp.row_id(r) for r in rows if r["language"] == lang)
        assert [r["id"] for r in a if r["language"] == lang] == mine[:2]
    assert all(r["category"] == r["label_id"].split("/")[0] and r["subcategory"] == r["label_id"].split("/")[1] for r in a)
    assert all(r["language"] != "en" for r in a)


def test_pick_rows_with_fewer_rows_takes_what_exists():
    assert [r["language"] for r in cmp.pick_rows(gold_rows()[4:6])] == ["hi", "hi"]
    assert cmp.pick_rows([]) == []


def test_clip_limits_printed_text():
    assert len(cmp.clip("a " * 100)) <= 80 and cmp.clip("short  text") == "short text"


def test_projected_calls_per_minute():
    assert cmp.projected_calls_per_minute(1000) == 8
    assert cmp.projected_calls_per_minute(2999.9) == 2
    assert cmp.projected_calls_per_minute(9000) == 0
    assert cmp.projected_calls_per_minute(None) is None and cmp.projected_calls_per_minute(0) is None


def test_usage_numbers_derives_total_and_tolerates_junk():
    assert cmp.usage_numbers({"prompt_tokens": 5, "completion_tokens": 7}) == {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12}
    assert cmp.usage_numbers(None) == {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
    assert cmp.usage_numbers({"total_tokens": "x"})["total_tokens"] is None


def test_token_window_waits_until_old_calls_leave_the_window():
    now = [0.0]
    w = cmp.TokenWindow(7000, 60.0, clock=lambda: now[0])
    assert w.wait_needed(3000) == 0
    w.record(3000)
    now[0] = 10.0
    w.record(3000)
    assert w.used() == 6000 and w.wait_needed(900) == 0
    assert w.wait_needed(2000) == pytest.approx(50.0)           # the first 3000 leaves at t=60
    assert w.wait_needed(5000) == pytest.approx(60.0)           # both must leave; the second at t=70
    now[0] = 61.0
    assert w.used() == 3000 and w.wait_needed(2000) == 0


def test_token_window_that_can_never_fit_waits_for_an_empty_window():
    now = [0.0]
    w = cmp.TokenWindow(1000, 60.0, clock=lambda: now[0])
    w.record(500)
    assert w.wait_needed(5000) == pytest.approx(60.0)
    assert cmp.TokenWindow(1000).wait_needed(5000) == 0


def test_summarise_counts_and_median():
    calls = [
        {"status": "ok", "answered": True, "schema_valid": True, "cat_ok": True, "sub_ok": True, "provider_ms": 1000, "total_tokens": 1000, "prompt_tokens": 900, "completion_tokens": 100,
         "modes_worked": ["json_schema"]},
        {"status": "ok", "answered": True, "schema_valid": True, "cat_ok": True, "sub_ok": False, "provider_ms": 3000, "total_tokens": 2000, "prompt_tokens": 1800, "completion_tokens": 200,
         "modes_worked": ["json_object"], "json_schema_rejected": True},
        {"status": "provider_error", "answered": False, "schema_valid": False, "error": "ProviderUnavailable: groq: HTTP 429 (Rate limit reached)", "provider_ms": 50},
        {"status": "skipped"},
    ]
    s = cmp.summarise("m", calls)
    assert (s["rows_planned"], s["rows_called"], s["schema_valid"], s["category_agree"], s["subcategory_agree"]) == (4, 3, 2, 2, 1)
    assert s["median_provider_ms"] == 2000 and s["avg_total_tokens"] == 1500.0 and s["max_total_tokens"] == 2000
    assert s["projected_calls_per_min_at_tpm"] == 5 and s["any_call_over_tpm"] is False
    assert s["structured_mode"] == "json_object+json_schema" and s["json_schema_rejected"] is True
    assert "429" in s["errors"][0]


def test_summarise_flags_a_call_over_the_limit_and_handles_no_data():
    assert cmp.summarise("m", [{"status": "ok", "answered": True, "total_tokens": 8500}])["any_call_over_tpm"] is True
    s = cmp.summarise("m", [{"status": "skipped"}])
    assert s["avg_total_tokens"] is None and s["projected_calls_per_min_at_tpm"] is None and s["median_provider_ms"] is None


def test_table_has_one_line_per_model_and_no_none_text():
    t = cmp.table([cmp.summarise("a", [{"status": "skipped"}]), cmp.summarise("b", [])])
    assert len(t.splitlines()) == 4 and "None" not in t


# ------------------------------------------------------------------------------------------ run loop on the real adapter (mock transport)
def test_run_model_valid_answers_agree_with_gold_and_record_usage():
    rows = cmp.pick_rows(gold_rows())
    bodies = []

    def handler(req):
        bodies.append(json.loads(req.content))
        return httpx.Response(200, json=chat(answer("roads", "pothole")))

    calls, slept = run(rows, handler)
    assert len(calls) == 6 and all(c["schema_valid"] and c["status"] == "ok" for c in calls)
    assert [c["sub_ok"] for c in calls] == [r["subcategory"] == "pothole" for r in rows]
    assert all(c["total_tokens"] == 1000 and c["http_requests"] == [{"mode": "json_schema", "status": 200}] for c in calls)
    assert all(c["provider_ms"] is not None and c["modes_worked"] == ["json_schema"] for c in calls)
    assert all(b["response_format"]["type"] == "json_schema" and b["model"] == "model-a" for b in bodies)
    assert not any("image_url" in json.dumps(b) for b in bodies)
    assert not slept                                               # 6 x 1000 tokens fit the 7000 window: no pacing needed


def test_run_model_paces_with_the_window_and_never_exceeds_the_budget():
    now = [0.0]
    w = cmp.TokenWindow(7000, 60.0, clock=lambda: now[0])
    sleeps = []

    def sleep(s):
        sleeps.append(s)
        now[0] += s

    rows = cmp.pick_rows(gold_rows())
    peak = []

    def handler(req):
        peak.append(w.used() + 3000)
        return httpx.Response(200, json=chat(answer(), usage=(2800, 200)))

    calls = cmp.run_model("model-a", rows, factory(handler), window=w, sleep=sleep, log=lambda s: None)
    assert len(calls) == 6 and sleeps and max(peak) <= 7000


def test_run_model_marks_degraded_when_the_answer_fails_validation():
    rows = cmp.pick_rows(gold_rows())[:2]
    replies = iter([chat({"title": "only a title"}), chat(answer(severity="URGENT"))])
    calls, _ = run(rows, lambda req: httpx.Response(200, json=next(replies)))
    assert [c["schema_valid"] for c in calls] == [False, False]
    assert all(c["status"] == "degraded" and c["fallback_reason"] and not c["cat_ok"] and c["total_tokens"] == 1000 for c in calls)


def test_run_model_non_json_answer_is_invalid_not_a_provider_error():
    rows = cmp.pick_rows(gold_rows())[:2]
    bad = {"model": "m", "choices": [{"message": {"content": "sorry, no"}, "finish_reason": "stop"}], "usage": {"total_tokens": 700, "prompt_tokens": 650, "completion_tokens": 50}}
    calls, _ = run(rows, lambda req: httpx.Response(200, json=bad))
    assert all(c["status"] == "degraded" and c["answered"] and not c["schema_valid"] and "ProviderResponseInvalid" in c["error"] for c in calls)


def test_run_model_records_json_schema_rejection_and_stays_in_json_object():
    rows = cmp.pick_rows(gold_rows())[:3]
    seen = []

    def handler(req):
        mode = json.loads(req.content)["response_format"]["type"]
        seen.append(mode)
        if mode == "json_schema":
            return httpx.Response(400, json={"error": {"message": "response_format json_schema is not supported by this model"}})
        return httpx.Response(200, json=chat(answer("water_supply", "pipe_leakage")))

    calls, _ = run(rows, handler)
    assert seen == ["json_schema", "json_object", "json_object", "json_object"]            # one probe, then the adapter stays in JSON mode
    assert calls[0]["json_schema_rejected"] and calls[0]["modes_worked"] == ["json_object"]
    assert all(c["schema_valid"] for c in calls)
    s = cmp.summarise("model-a", calls)
    assert s["json_schema_rejected"] and s["structured_mode"] == "json_object"


def test_run_model_stops_on_429_records_exact_message_and_does_not_retry():
    rows = cmp.pick_rows(gold_rows())
    n = []

    def handler(req):
        n.append(1)
        if len(n) == 3:
            return httpx.Response(429, headers={"retry-after": "12"}, json={"error": {"message": "Rate limit reached for model `model-a` on tokens per minute (TPM): Limit 8000, Used 7900"}})
        return httpx.Response(200, json=chat(answer()))

    calls, _ = run(rows, handler)
    assert len(n) == 3                                              # no retry, no further calls
    assert [c["status"] for c in calls] == ["ok", "ok", "provider_error", "skipped", "skipped", "skipped"]
    assert calls[2]["http_status"] == 429 and "Rate limit reached for model `model-a` on tokens per minute (TPM): Limit 8000, Used 7900" in calls[2]["error"]
    assert calls[2]["quota"]["retry_delay_s"] == 12
    assert "SECRET-KEY-123" not in json.dumps(calls)
    s = cmp.summarise("model-a", calls)
    assert s["rows_called"] == 3 and s["errors"] and "429" in s["errors"][0]


@pytest.mark.parametrize("status", [400, 404])
def test_run_model_rejected_model_id_stops_with_the_provider_message(status):
    rows = cmp.pick_rows(gold_rows())
    n = []

    def handler(req):
        n.append(1)
        return httpx.Response(status, json={"error": {"message": "The model `model-a` does not exist or you do not have access to it.", "code": "model_not_found"}})

    calls, _ = run(rows, handler)
    assert calls[0]["status"] == "provider_error" and "does not exist" in calls[0]["error"]
    assert all(c["status"] == "skipped" for c in calls[1:])
    assert len(n) <= 2                                              # at most the json_schema attempt and the one json_object probe
    assert not any(c.get("schema_valid") for c in calls)


def test_run_model_never_exceeds_the_http_request_cap():
    rows = cmp.pick_rows(gold_rows())
    inner = factory(lambda req: httpx.Response(200, json=chat(answer())))("model-a")
    rec = cmp.Recorder(inner, max_http=2)
    from ai.inference.provider import InputPart
    for _ in range(2):
        rec.structured_completion(task="intake", instructions="i", parts=[InputPart.of_text("x")], schema_name="s", json_schema={"type": "object"})
    with pytest.raises(Exception, match="cap reached"):
        rec.structured_completion(task="intake", instructions="i", parts=[InputPart.of_text("x")], schema_name="s", json_schema={"type": "object"})
    assert rec.http_total == 2 and len(rows) == 6


def test_main_dry_run_makes_no_call_and_prints_rows(monkeypatch, capsys, tmp_path):
    gold = tmp_path / "gold.csv"
    lines = ["text,label_id,language,notes,provenance"]
    for lang in ("hi", "mr", "hi-Latn"):
        for i in range(3):
            lines.append(f"complaint {lang} {i},roads/pothole,{lang},n,llm_authored_claude")
    gold.write_text("\n".join(lines), encoding="utf-8")
    monkeypatch.setattr(cmp, "make_groq_provider", lambda m: pytest.fail("a provider was built in a dry run"))
    assert cmp.main(["--models", "model-a", "model-b", "--gold", str(gold), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "planned real calls: 12" in out and "model-a, model-b" in out and "dry run: no call made" in out
    assert out.count("roads/pothole") == 6


def test_main_requires_two_models():
    with pytest.raises(SystemExit):
        cmp.main(["--dry-run"])
    with pytest.raises(SystemExit):
        cmp.main(["--models", "only-one", "--dry-run"])
