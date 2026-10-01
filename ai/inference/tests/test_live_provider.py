"""LIVE provider smoke tests. Skipped unless real credentials AND model IDs are configured.

    OPENAI_API_KEY=... AI_INTAKE_MODEL=... AI_EMBEDDING_MODEL=... pytest -m requires_provider -rs

These have NOT been run in the authoring environment (egress blocked, no credentials). Validate the model IDs
against the provider's current catalogue first (system design Sections 30 and 64).
"""
import os

import pytest

from ai.inference.config import ProviderSettings
from ai.inference.providers.openai_provider import OpenAIProvider
from ai.inference.schemas import IntakeRequest

pytestmark = pytest.mark.requires_provider


def live_settings(*need):
    s = ProviderSettings.from_env()
    missing = [n for n in need if not s.model_for(n)]
    if s.api_key is None or missing:
        pytest.skip(f"requires OPENAI_API_KEY and model env vars for {need or 'provider'} (missing: {missing})")
    return s


def test_live_embeddings():
    p = OpenAIProvider(live_settings("embedding"))
    res = p.embed(["pothole near the school", "सड़क पर गड्ढा"])
    assert len(res.vectors) == 2 and res.dimension > 100


def test_live_structured_intake_end_to_end():
    from ai.inference.service import AIService
    s = live_settings("intake")
    ai = AIService.from_env(dict(os.environ))
    r = ai.analyze_intake(IntakeRequest(text="Large pothole near the school gate on Station Road, children nearly fell"))
    assert r.ai_metadata.source == "provider", r.warnings
    assert r.proposal.category == "roads" and 0 <= r.confidence <= 1 and r.requires_confirmation and s.model_for("intake")
