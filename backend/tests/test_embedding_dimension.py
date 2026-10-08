"""AI_EMBEDDING_DIM (gemini-embedding-001 at 768 dimensions): the request asks for the size, the length is checked, the vector is L2-normalised. httpx mock transport only."""
import json
import math

import httpx
import pytest

from ai.inference.errors import ProviderResponseInvalid
from backend.ai_gateway.providers import ChatCompletionsProvider, build_provider_from_env

MODELS = {"embedding": "gemini-embedding-001"}


def provider(handler, **kw):
    return ChatCompletionsProvider("gemini", "https://g.test/v1beta/openai", "k", MODELS, client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None, **kw)


def reply(vectors):
    return {"model": "gemini-embedding-001", "data": [{"index": i, "embedding": v} for i, v in enumerate(vectors)]}


def test_dimension_is_requested_and_vectors_are_normalised_to_unit_length():
    seen = {}

    def handler(req):
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json=reply([[3.0] + [0.0] * 3 + [4.0] * 0 + [4.0] + [0.0] * 3, [1.0] * 8]))

    out = provider(handler, embedding_dim=8).embed(["a", "b"])
    assert seen["body"]["dimensions"] == 8 and seen["body"]["model"] == "gemini-embedding-001" and seen["body"]["input"] == ["a", "b"]
    assert [len(v) for v in out.vectors] == [8, 8]
    assert all(math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-9) for v in out.vectors)
    assert out.vectors[0][0] == pytest.approx(0.6) and out.vectors[0][4] == pytest.approx(0.8)          # 3-4-5 direction preserved


def test_wrong_length_is_refused_not_stored():
    p = provider(lambda req: httpx.Response(200, json=reply([[0.1] * 5])), embedding_dim=8)
    with pytest.raises(ProviderResponseInvalid, match="5 dimensions, AI_EMBEDDING_DIM is 8"):
        p.embed(["a"])


def test_zero_vector_is_refused():
    with pytest.raises(ProviderResponseInvalid):
        provider(lambda req: httpx.Response(200, json=reply([[0.0] * 8])), embedding_dim=8).embed(["a"])


def test_without_a_configured_dimension_nothing_is_requested_and_vectors_are_still_unit_length():
    seen = {}

    def handler(req):
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json=reply([[2.0, 0.0]]))

    out = provider(handler).embed(["a"])
    assert "dimensions" not in seen["body"] and out.vectors == [[1.0, 0.0]]


def test_factory_reads_ai_embedding_dim_and_rejects_nonsense():
    env = {"GEMINI_API_KEY": "g", "AI_INTAKE_MODEL": "m", "AI_EMBEDDING_MODEL": "gemini-embedding-001", "AI_EMBEDDING_DIM": "768"}
    assert build_provider_from_env(env).routes["embedding"]._embedding_dim == 768
    assert build_provider_from_env({k: v for k, v in env.items() if k != "AI_EMBEDDING_DIM"}).routes["embedding"]._embedding_dim is None
    for bad in ("seven", "0", "-3", "768.0"):
        with pytest.raises(ValueError, match="AI_EMBEDDING_DIM"):
            build_provider_from_env({**env, "AI_EMBEDDING_DIM": bad})


def test_provider_error_messages_name_the_cause_without_the_key():
    from ai.inference.errors import ProviderUnavailable
    body = [{"error": {"code": 429, "message": "Quota exceeded for metric generate_content_free_tier_requests, limit: 20, model: m. key=SECRET-KEY-123 please retry", "status": "RESOURCE_EXHAUSTED"}}]
    p = ChatCompletionsProvider("gemini", "https://g.test/v1beta/openai", "SECRET-KEY-123", MODELS, max_retries=0, sleep=lambda s: None,
                                client=httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(429, json=body))))
    with pytest.raises(ProviderUnavailable) as e:
        p.embed(["a"])
    assert "HTTP 429" in str(e.value) and "Quota exceeded" in str(e.value) and "limit: 20" in str(e.value) and "key=***" in str(e.value) and "SECRET-KEY-123" not in str(e.value)
    q = provider(lambda req: httpx.Response(500, text="<html>boom</html>"), max_retries=0)
    with pytest.raises(ProviderUnavailable) as e2:
        q.embed(["a"])
    assert str(e2.value) == "gemini: HTTP 500"
