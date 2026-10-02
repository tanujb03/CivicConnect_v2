"""Free / OpenAI-compatible providers: request shapes, fallbacks, throttling, routing and env wiring — all on httpx mock transports (no network, no keys)."""
import base64
import json
import os
import sys

import httpx
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from fastapi.testclient import TestClient  # noqa: E402

from ai.inference.errors import ProviderNotConfigured, ProviderResponseInvalid, ProviderUnavailable  # noqa: E402
from ai.inference.provider import InputPart, ToolSpec  # noqa: E402
from ai.inference.schemas import EvidenceInput  # noqa: E402
from backend.ai_gateway import configure_gateway  # noqa: E402
from backend.ai_gateway.providers import ChatCompletionsProvider, CompositeProvider, build_provider_from_env  # noqa: E402
from backend.core.security import create_access_token  # noqa: E402
from backend.main import app  # noqa: E402
from backend.tests.test_ai_gateway import Env  # noqa: E402

SCHEMA = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"], "additionalProperties": False}
MODELS = {"intake": "m-intake", "triage": "m-triage", "copilot": "m-copilot", "embedding": "m-embed", "transcription": "m-stt"}


def provider(handler, **kw):
    kw.setdefault("sleep", lambda s: None)
    return ChatCompletionsProvider("testbackend", "https://api.example.test/v1", "SECRET-KEY-123", MODELS, client=httpx.Client(transport=httpx.MockTransport(handler)), **kw)


def chat(content, **extra):
    return {"model": "served-model", "choices": [{"message": {"content": content}, "finish_reason": "stop"}], "usage": {"total_tokens": 5}, **extra}


def test_structured_request_shape_and_image_data_url():
    seen = {}

    def handler(req: httpx.Request):
        seen.update(url=str(req.url), auth=req.headers["authorization"], body=json.loads(req.content))
        return httpx.Response(200, json=chat('{"a": "x"}'))

    img = EvidenceInput(evidence_id="e", media_type="IMAGE", mime_type="image/png", data=b"\x89PNG")
    r = provider(handler).structured_completion(task="intake", instructions="be careful", parts=[InputPart.of_text("hello"), InputPart.of_image(img)], schema_name="s", json_schema=SCHEMA)
    assert r.data == {"a": "x"} and r.model == "served-model" and seen["url"] == "https://api.example.test/v1/chat/completions" and seen["auth"] == "Bearer SECRET-KEY-123"
    b = seen["body"]
    assert b["model"] == "m-intake" and b["messages"][0] == {"role": "system", "content": "be careful"}
    assert b["response_format"]["type"] == "json_schema" and b["response_format"]["json_schema"]["schema"] == SCHEMA
    content = b["messages"][1]["content"]
    assert content[0] == {"type": "text", "text": "hello"} and content[1]["image_url"]["url"] == "data:image/png;base64," + base64.b64encode(b"\x89PNG").decode()
    assert "SECRET-KEY-123" not in repr(provider(handler))


def test_fenced_json_is_accepted_and_garbage_or_refusals_are_not():
    ok = provider(lambda r: httpx.Response(200, json=chat('```json\n{"a": "y"}\n```')))
    assert ok.structured_completion(task="intake", instructions="i", parts=[InputPart.of_text("t")], schema_name="s", json_schema=SCHEMA).data == {"a": "y"}
    for body in (chat("no json here"), chat("[1,2]"), {"choices": []}, {"choices": [{"message": {"content": None, "refusal": "no"}, "finish_reason": "stop"}]}):
        with pytest.raises(ProviderResponseInvalid):
            provider(lambda r, b=body: httpx.Response(200, json=b)).structured_completion(task="intake", instructions="i", parts=[InputPart.of_text("t")], schema_name="s", json_schema=SCHEMA)


def test_a_400_on_json_schema_falls_back_once_to_json_mode_with_the_schema_in_the_prompt():
    calls = []

    def handler(req):
        body = json.loads(req.content)
        calls.append(body["response_format"]["type"])
        return httpx.Response(400, json={"error": "unsupported"}) if body["response_format"]["type"] == "json_schema" else httpx.Response(200, json=chat('{"a": "z"}'))

    r = provider(handler).structured_completion(task="intake", instructions="i", parts=[InputPart.of_text("t")], schema_name="s", json_schema=SCHEMA)
    assert r.data == {"a": "z"} and calls == ["json_schema", "json_object"]


def test_retry_after_is_honoured_and_failures_are_provider_unavailable():
    sleeps, n = [], {"n": 0}

    def flaky(req):
        n["n"] += 1
        return httpx.Response(429, headers={"retry-after": "3"}) if n["n"] < 3 else httpx.Response(200, json=chat('{"a": "ok"}'))

    r = provider(flaky, sleep=sleeps.append).structured_completion(task="intake", instructions="i", parts=[InputPart.of_text("t")], schema_name="s", json_schema=SCHEMA)
    assert r.data == {"a": "ok"} and n["n"] == 3 and sleeps[:2] == [3.0, 3.0]
    with pytest.raises(ProviderUnavailable) as e:
        provider(lambda r: httpx.Response(401)).structured_completion(task="intake", instructions="i", parts=[InputPart.of_text("t")], schema_name="s", json_schema=SCHEMA)
    assert e.value.status_code == 401
    with pytest.raises(ProviderUnavailable):
        provider(lambda r: (_ for _ in ()).throw(httpx.ConnectError("down")), max_retries=1).structured_completion(task="intake", instructions="i", parts=[InputPart.of_text("t")],
                                                                                                            schema_name="s", json_schema=SCHEMA)


def test_rpm_throttle_spaces_requests_for_free_tier_limits():
    now, sleeps = {"t": 100.0}, []

    def sleep(s):
        sleeps.append(round(s, 3))
        now["t"] += s

    p = provider(lambda r: httpx.Response(200, json=chat('{"a": "1"}')), rpm=10, sleep=sleep, clock=lambda: now["t"])
    for _ in range(3):
        p.structured_completion(task="intake", instructions="i", parts=[InputPart.of_text("t")], schema_name="s", json_schema=SCHEMA)
    assert sleeps == [6.0, 6.0]                                        # 10 requests/minute -> one every 6 s after the first


def test_embeddings_batch_and_count_mismatch():
    def handler(req):
        inp = json.loads(req.content)["input"]
        return httpx.Response(200, json={"model": "e", "data": [{"index": i, "embedding": [float(i), 1.0]} for i in range(len(inp))]})

    r = provider(handler).embed([f"t{i}" for i in range(130)])
    assert len(r.vectors) == 130 and r.dimension == 2 and r.model == "e"
    with pytest.raises(ProviderResponseInvalid):
        provider(lambda req: httpx.Response(200, json={"data": []})).embed(["a"])


def test_transcription_uses_the_audio_endpoint_with_the_language_hint():
    seen = {}

    def handler(req):
        seen["url"], seen["ct"], seen["body"] = str(req.url), req.headers["content-type"], req.content
        return httpx.Response(200, json={"text": " paani nahi aa raha ", "language": "hi"})

    t = provider(handler).transcribe(EvidenceInput(evidence_id="a1", media_type="AUDIO", mime_type="audio/webm", data=b"RIFF"), "hi")
    assert t.text == "paani nahi aa raha" and t.language == "hi" and seen["url"].endswith("/audio/transcriptions") and seen["ct"].startswith("multipart/form-data")
    assert b'name="language"' in seen["body"] and b"hi" in seen["body"] and b'name="model"' in seen["body"]
    with pytest.raises(ProviderResponseInvalid):
        provider(lambda r: httpx.Response(200, json={"text": ""})).transcribe(EvidenceInput(evidence_id="a", media_type="AUDIO", data=b"x"))


def test_plan_tools_parses_calls_and_marks_bad_arguments_visibly():
    body = {"model": "m", "choices": [{"message": {"content": None, "tool_calls": [
        {"function": {"name": "search_cases", "arguments": '{"category": "sanitation"}'}}, {"function": {"name": "count_cases", "arguments": "{bad"}}]}}]}
    plan = provider(lambda r: httpx.Response(200, json=body)).plan_tools(instructions="i", query="q", tools=[ToolSpec("search_cases", "d", {"type": "object"})])
    assert [(c.name, c.arguments) for c in plan.calls] == [("search_cases", {"category": "sanitation"}), ("count_cases", {"__raw__": "{bad"})]


def test_missing_key_or_model_is_not_configured():
    with pytest.raises(ProviderNotConfigured):
        ChatCompletionsProvider("x", "https://a.test", None, MODELS)
    p = ChatCompletionsProvider("x", "https://a.test", "k", {}, client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200))))
    with pytest.raises(ProviderNotConfigured):
        p.embed(["a"])


# ------------------------------------------------------------------------------------------------ routing + env
class Tag:
    def __init__(self, name, models):
        self.name, self.models, self.calls = name, models, []

    def model_for(self, task):
        return self.models.get(task)

    def structured_completion(self, **kw):
        self.calls.append(("structured", kw["task"]))
        return kw["task"]

    def embed(self, texts):
        self.calls.append(("embed",))
        return "embedded"

    def transcribe(self, audio, language_hint=None):
        self.calls.append(("transcribe",))
        return "transcribed"

    def plan_tools(self, **kw):
        self.calls.append(("plan",))
        return "planned"


def test_composite_routes_by_task_and_degrades_for_unrouted_tasks():
    g, w = Tag("gemini", {"intake": "a"}), Tag("groq", {"transcription": "w"})
    c = CompositeProvider({"intake": g, "transcription": w})
    assert c.name == "composite(gemini,groq)" and c.model_for("intake") == "a" and c.model_for("transcription") == "w" and c.model_for("copilot") is None
    assert c.structured_completion(task="intake", instructions="", parts=[], schema_name="s", json_schema={}) == "intake" and c.transcribe(None) == "transcribed" and g.calls == [("structured", "intake")]
    with pytest.raises(ProviderNotConfigured):
        c.embed(["x"])


def test_factory_builds_routes_from_the_environment():
    env = {"GEMINI_API_KEY": "g", "GROQ_API_KEY": "q", "AI_INTAKE_MODEL": "gem-intake", "AI_ANALYTICS_MODEL": "gem-an", "AI_TRANSCRIPTION_MODEL": "whisper-x", "AI_EMBEDDING_MODEL": "gem-emb"}
    p = build_provider_from_env(env)
    assert p.routes["intake"].name == "gemini" and p.routes["transcription"].name == "groq" and p.routes["embedding"].name == "gemini"
    assert p.model_for("intake") == "gem-intake" and p.model_for("triage") == "gem-intake" and p.model_for("copilot") == "gem-an"        # same fallbacks as ai.inference.config
    assert p.model_for("resolution") == "gem-intake"
    p2 = build_provider_from_env({**env, "AI_ROUTES": "intake=groq,bogus=gemini,copilot=openai"})
    assert p2.routes["intake"].name == "groq" and "bogus" not in p2.routes and p2.routes["copilot"].name == "gemini"                      # unknown task / unkeyed backend ignored
    assert build_provider_from_env({"AI_INTAKE_MODEL": "x"}) is None and build_provider_from_env({"GEMINI_API_KEY": "g"}) is None       # no key, or key but no model ids
    cf = build_provider_from_env({"CLOUDFLARE_API_TOKEN": "t", "CLOUDFLARE_ACCOUNT_ID": "acc1", "AI_INTAKE_MODEL": "m"})
    assert cf.routes["intake"]._base == "https://api.cloudflare.com/client/v4/accounts/acc1/ai/v1"
    assert build_provider_from_env({"CLOUDFLARE_API_TOKEN": "t", "AI_INTAKE_MODEL": "m"}) is None                                       # account id missing
    assert build_provider_from_env({**env, "AI_GEMINI_RPM": "7"}).routes["intake"]._min_gap == pytest.approx(60 / 7)


# ------------------------------------------------------------------------------------------------ through the real endpoint
def test_intake_endpoint_works_with_a_free_openai_compatible_backend():
    intake = {"title": "Pothole near school", "description": "Large pothole", "category": "roads", "subcategory": "pothole", "severity": "HIGH", "language": "en",
              "transcript": None, "confidence": 0.9, "reasons": ["text says pothole"], "image_observations": []}
    seen = {}

    def handler(req):
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json=chat(json.dumps(intake)))

    env = Env(ChatCompletionsProvider("gemini", "https://g.test/v1beta/openai", "k", {"intake": "gem-x"}, client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None))
    configure_gateway(env.gateway)
    try:
        r = TestClient(app).post("/api/v1/cases/intake/analyze", headers={"Authorization": f"Bearer {create_access_token('u1', 'citizen')}"}, json={"text": "pothole near the school"})
    finally:
        configure_gateway(None)
    b = r.json()
    assert r.status_code == 200 and b["proposal"]["category"] == "roads" and b["ai_metadata"]["source"] == "provider" and b["ai_metadata"]["provider"] == "gemini"
    assert seen["body"]["model"] == "gem-x" and "citizen text" in seen["body"]["messages"][0]["content"].lower() or seen["body"]["messages"]


# ------------------------------------------------------------------------------------------------ .env loading + model listing + live-check CLI
def test_env_file_loader_exports_only_missing_variables_and_treats_comment_values_as_empty(tmp_path):
    from backend.ai_gateway.envfile import load_env_file, parse
    f = tmp_path / ".env"
    f.write_text('GEMINI_API_KEY=abc\nAI_INTAKE_MODEL=   # pick from the list\nexport GROQ_API_KEY="q q"\nKEEP=file\n', encoding="utf-8")
    assert parse(f.read_text()) == {"GEMINI_API_KEY": "abc", "AI_INTAKE_MODEL": "", "GROQ_API_KEY": "q q", "KEEP": "file"}
    env = {"KEEP": "real"}
    assert sorted(load_env_file([f], env)) == ["GEMINI_API_KEY", "GROQ_API_KEY"] and env["KEEP"] == "real" and "AI_INTAKE_MODEL" not in env
    assert load_env_file([tmp_path / "missing"], {}) == []


def test_settings_do_not_crash_on_extra_variables_in_dotenv(tmp_path, monkeypatch):
    from backend.core.config import Settings
    (tmp_path / ".env").write_text("GEMINI_API_KEY=x\nPOSTGRES_DB=demo\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert Settings().POSTGRES_DB == "demo"


def test_list_models_normalises_ids():
    p = provider(lambda r: httpx.Response(200, json={"data": [{"id": "models/gem-a"}, {"id": "gem-b"}, {"nope": 1}]}))
    assert p.list_models() == ["gem-a", "gem-b"]
    with pytest.raises(ProviderUnavailable):
        provider(lambda r: httpx.Response(403)).list_models()


def test_live_check_cli_requires_keys_and_never_prints_them(capsys, monkeypatch, tmp_path):
    from backend.ai_gateway.providers import live_check
    for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "CLOUDFLARE_API_TOKEN", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(live_check, "load_env_file", lambda: [])
    assert live_check.main([]) == 2 and "No backend has a key" in capsys.readouterr().out
    monkeypatch.setenv("GEMINI_API_KEY", "SECRET-VALUE-XYZ")
    assert live_check.main([]) == 2 and "SECRET-VALUE-XYZ" not in capsys.readouterr().out          # key but no model ids
