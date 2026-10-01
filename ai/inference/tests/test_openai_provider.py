"""OpenAIProvider against httpx.MockTransport. NOT live API tests — see test_live_provider.py."""
import base64
import json

import httpx
import pytest
from pydantic import SecretStr

from ai.inference.config import ProviderSettings
from ai.inference.errors import ProviderNotConfigured, ProviderResponseInvalid, ProviderUnavailable
from ai.inference.provider import AIProvider, InputPart, ToolSpec
from ai.inference.providers.openai_provider import OpenAIProvider
from ai.inference.schemas import EvidenceInput

SECRET = "sk-test-SECRET-123"
MODELS = {"intake": "m-intake", "embedding": "m-emb", "transcription": "m-asr", "copilot": "m-cop"}


def settings(**kw):
    base = dict(provider="openai", api_key=SecretStr(SECRET), base_url="https://example.test/v1", models=MODELS, max_retries=1)
    return ProviderSettings(**{**base, **kw})


def make(handler, **kw):
    sleeps = []
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenAIProvider(settings(**kw), client=client, sleep=sleeps.append), sleeps


def msg(text):
    return {"model": "m-intake-2026", "status": "completed", "usage": {"total_tokens": 5},
            "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]}


def test_conforms_to_provider_protocol():
    p, _ = make(lambda r: httpx.Response(200, json={}))
    assert isinstance(p, AIProvider) and p.name == "openai"


def test_structured_request_shape_and_parsing():
    seen = {}

    def handler(req: httpx.Request):
        seen["url"], seen["auth"], seen["body"] = str(req.url), req.headers["authorization"], json.loads(req.content)
        return httpx.Response(200, json=msg('{"a": 1}'))

    p, _ = make(handler)
    img = EvidenceInput(evidence_id="i", media_type="IMAGE", data=b"IMGBYTES", mime_type="image/png")
    res = p.structured_completion(task="intake", instructions="INSTR", parts=[InputPart.of_text("hello"), InputPart.of_image(img)],
                                  schema_name="s", json_schema={"type": "object"})
    b = seen["body"]
    assert seen["url"] == "https://example.test/v1/responses" and seen["auth"] == f"Bearer {SECRET}"
    assert b["model"] == "m-intake" and b["instructions"] == "INSTR" and b["store"] is False
    assert b["text"]["format"] == {"type": "json_schema", "name": "s", "schema": {"type": "object"}, "strict": True}
    content = b["input"][0]["content"]
    assert content[0] == {"type": "input_text", "text": "hello"}
    assert content[1] == {"type": "input_image", "image_url": "data:image/png;base64," + base64.b64encode(b"IMGBYTES").decode()}
    assert res.data == {"a": 1} and res.model == "m-intake-2026" and res.usage == {"total_tokens": 5}


def test_signed_url_images_are_passed_by_reference():
    seen = {}
    p, _ = make(lambda r: (seen.update(b=json.loads(r.content)), httpx.Response(200, json=msg("{}")))[1])
    p.structured_completion(task="intake", instructions="i", schema_name="s", json_schema={},
                            parts=[InputPart.of_image(EvidenceInput(evidence_id="i", media_type="IMAGE", url="https://signed/x"))])
    assert seen["b"]["input"][0]["content"][0]["image_url"] == "https://signed/x"


@pytest.mark.parametrize("body", [
    {"output": [{"type": "message", "content": [{"type": "refusal", "refusal": "no"}]}]},
    {"status": "incomplete", "output": []},
    {"output": []},
    msg("not json at all"),
    msg("[1, 2]"),
])
def test_bad_provider_outputs_are_rejected(body):
    p, _ = make(lambda r: httpx.Response(200, json=body))
    with pytest.raises(ProviderResponseInvalid):
        p.structured_completion(task="intake", instructions="i", parts=[InputPart.of_text("x")], schema_name="s", json_schema={})


def test_non_json_http_body_is_invalid():
    p, _ = make(lambda r: httpx.Response(200, content=b"<html>"))
    with pytest.raises(ProviderResponseInvalid):
        p.structured_completion(task="intake", instructions="i", parts=[InputPart.of_text("x")], schema_name="s", json_schema={})


def test_retry_on_429_then_success():
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(429) if len(calls) == 1 else httpx.Response(200, json=msg("{}"))

    p, sleeps = make(handler)
    p.structured_completion(task="intake", instructions="i", parts=[InputPart.of_text("x")], schema_name="s", json_schema={})
    assert len(calls) == 2 and sleeps == [0.5]


def test_persistent_5xx_raises_unavailable_with_status():
    p, _ = make(lambda r: httpx.Response(503))
    with pytest.raises(ProviderUnavailable) as e:
        p.structured_completion(task="intake", instructions="i", parts=[InputPart.of_text("x")], schema_name="s", json_schema={})
    assert e.value.status_code == 503


def test_auth_errors_are_not_retried():
    calls = []
    p, _ = make(lambda r: (calls.append(1), httpx.Response(401, json={"error": {"message": f"bad key {SECRET}"}}))[1])
    with pytest.raises(ProviderUnavailable) as e:
        p.structured_completion(task="intake", instructions="i", parts=[InputPart.of_text("x")], schema_name="s", json_schema={})
    assert len(calls) == 1 and SECRET not in str(e.value)


def test_transport_errors_become_unavailable():
    def handler(req):
        raise httpx.ConnectError("boom")

    p, _ = make(handler)
    with pytest.raises(ProviderUnavailable):
        p.embed(["x"])


def test_embeddings_are_batched_and_reordered():
    batches = []

    def handler(req):
        inp = json.loads(req.content)["input"]
        batches.append(len(inp))
        rows = [{"index": i, "embedding": [float(inp[i].split("-")[1]), 0.0]} for i in range(len(inp))]
        return httpx.Response(200, json={"model": "m-emb-x", "data": list(reversed(rows))})

    p, _ = make(handler)
    res = p.embed([f"t-{i}" for i in range(100)])
    assert batches == [96, 4] and [v[0] for v in res.vectors] == [float(i) for i in range(100)]
    assert res.model == "m-emb-x" and res.dimension == 2


def test_embedding_count_mismatch_is_invalid():
    p, _ = make(lambda r: httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0]}]}))
    with pytest.raises(ProviderResponseInvalid):
        p.embed(["a", "b"])


def test_transcription_request_and_parsing():
    seen = {}

    def handler(req):
        seen["ct"], seen["body"] = req.headers["content-type"], req.content
        return httpx.Response(200, json={"text": " नमस्कार "})

    p, _ = make(handler)
    out = p.transcribe(EvidenceInput(evidence_id="a1", media_type="AUDIO", data=b"AUDIO", mime_type="audio/webm"), "hi")
    assert seen["ct"].startswith("multipart/form-data") and b"m-asr" in seen["body"] and b'name="language"' in seen["body"]
    assert out.text == "नमस्कार"


def test_transcription_requires_bytes_and_text():
    p, _ = make(lambda r: httpx.Response(200, json={"text": ""}))
    with pytest.raises(ProviderResponseInvalid):
        p.transcribe(EvidenceInput(evidence_id="a", media_type="AUDIO", url="https://x"))
    with pytest.raises(ProviderResponseInvalid):
        p.transcribe(EvidenceInput(evidence_id="a", media_type="AUDIO", data=b"x"))


def test_tool_plan_parsing():
    seen = {}

    def handler(req):
        seen["b"] = json.loads(req.content)
        return httpx.Response(200, json={"model": "m-cop", "output": [
            {"type": "function_call", "name": "search_cases", "arguments": '{"category": "sanitation"}', "call_id": "c1"},
            {"type": "function_call", "name": "count_cases", "arguments": "{not json", "call_id": "c2"}]})

    p, _ = make(handler)
    plan = p.plan_tools(instructions="plan", query="show me", tools=[ToolSpec("search_cases", "d", {"type": "object"})])
    assert seen["b"]["tools"][0]["type"] == "function" and seen["b"]["tools"][0]["name"] == "search_cases"
    assert plan.calls[0].arguments == {"category": "sanitation"} and "__raw__" in plan.calls[1].arguments


def test_secret_is_never_exposed():
    p, _ = make(lambda r: httpx.Response(200, json={}))
    assert SECRET not in repr(p) and SECRET not in repr(settings()) and SECRET not in str(settings())
    assert SECRET not in settings().model_dump_json()


def test_missing_key_or_model_is_not_configured():
    with pytest.raises(ProviderNotConfigured):
        OpenAIProvider(ProviderSettings(provider="openai", api_key=None))
    p, _ = make(lambda r: httpx.Response(200, json={}), models={})
    with pytest.raises(ProviderNotConfigured):
        p.embed(["x"])


def test_settings_from_env_never_hardcodes_models():
    s = ProviderSettings.from_env({})
    assert s.provider == "none" and s.models == {} and s.api_key is None
    s = ProviderSettings.from_env({"OPENAI_API_KEY": "k", "AI_INTAKE_MODEL": "a", "AI_ANALYTICS_MODEL": "b", "AI_EMBEDDING_MODEL": "c"})
    assert s.provider == "openai" and s.model_for("triage") == "a" and s.model_for("copilot") == "b" and s.model_for("embedding") == "c"
    assert s.model_for("transcription") is None
