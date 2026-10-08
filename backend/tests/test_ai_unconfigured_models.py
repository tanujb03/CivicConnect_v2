"""WP1 step 0: a key without any ``AI_*_MODEL`` id (the state of every .env on 2026-10-08) must degrade cleanly. No provider is built, no request leaves the process, and the AI
endpoints answer 200 with the documented degraded mode (rules and local models) instead of failing or guessing a model name."""
import httpx
import pytest

from backend.ai_gateway import configure_gateway
from backend.ai_gateway.providers import build_provider_from_env
from backend.ai_gateway.sql import build_sql_gateway

MODEL_VARS = ("AI_INTAKE_MODEL", "AI_TRIAGE_MODEL", "AI_RESOLUTION_MODEL", "AI_ANALYTICS_MODEL", "AI_COPILOT_MODEL", "AI_EMBEDDING_MODEL", "AI_TRANSCRIPTION_MODEL")


@pytest.fixture
def keyed_without_models(env, monkeypatch):
    for k in MODEL_VARS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-key-for-the-test")
    monkeypatch.setenv("GROQ_API_KEY", "dummy-key-for-the-test")

    def no_network(request):                                                    # any outgoing call is a bug: there is no model to call
        raise AssertionError(f"unexpected network call to {request.url}")
    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: real_client(*a, **{**k, "transport": httpx.MockTransport(no_network)}))
    configure_gateway(build_sql_gateway())
    return env


def test_keys_without_model_ids_build_no_provider():
    assert build_provider_from_env({"GEMINI_API_KEY": "g", "GROQ_API_KEY": "q"}) is None


def test_intake_analyze_degrades_to_rules_and_local_models_and_says_so(keyed_without_models):
    env = keyed_without_models
    env.make_user("citizen", "alice")
    r = env.client.post("/api/v1/cases/intake/analyze", headers=env.headers("alice"), json={"text": "There is a big pothole near the school gate on Station Road"})
    body = r.json()
    assert r.status_code == 200, body
    assert body["requires_confirmation"] is True
    meta = body["ai_metadata"]
    assert meta["source"] != "provider" and meta["provider"] in (None, "", "none", "rules"), meta
    assert body["warnings"], "a degraded answer must carry a visible warning"
    assert body["proposal"]["category"] is not None                              # the rules still produce a proposal


def test_embedding_is_skipped_visibly_when_no_embedding_model_is_configured(keyed_without_models):
    gw = build_sql_gateway()
    vec, model, source = gw._embed_text("pothole near the school", [])
    assert vec is None and not model
