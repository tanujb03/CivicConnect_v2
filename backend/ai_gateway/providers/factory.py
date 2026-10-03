"""Build the provider from environment variables (no model ID is hard-coded; every ID comes from configuration).

    GEMINI_API_KEY / GROQ_API_KEY / OPENROUTER_API_KEY / OPENAI_API_KEY / CLOUDFLARE_API_TOKEN (+ CLOUDFLARE_ACCOUNT_ID)   backends that have a key are available
    AI_<TASK>_MODEL                      per-task model id (same names as ai.inference: AI_INTAKE_MODEL, AI_TRIAGE_MODEL, AI_RESOLUTION_MODEL, AI_ANALYTICS_MODEL,
                                         AI_COPILOT_MODEL, AI_EMBEDDING_MODEL, AI_TRANSCRIPTION_MODEL; fallbacks as in ai.inference.config)
    AI_ROUTES="intake=gemini,transcription=groq"   optional task -> backend overrides; default: transcription -> groq if keyed, everything else -> the first keyed backend
                                         in the order gemini, groq, openrouter, cloudflare, openai
    AI_<BACKEND>_RPM                     requests-per-minute throttle for that backend (free tiers are rate limited), e.g. AI_GEMINI_RPM=10
    AI_<BACKEND>_BASE_URL                override a preset's base URL
    AI_<BACKEND>_STRUCTURED=json_object  for backends/models that reject json_schema response formats
The base URLs below are the providers' documented OpenAI-compatible endpoints as of authoring; confirm them in each provider's docs when you create the key.
"""
from __future__ import annotations

import logging
import os
from typing import Mapping

from ai.inference.config import _MODEL_ENV
from ai.inference.provider import AIProvider

from .composite import CompositeProvider
from .openai_compat import ChatCompletionsProvider

log = logging.getLogger("civicconnect.ai.factory")

PRESETS = {
    "gemini": {"key": "GEMINI_API_KEY", "base": "https://generativelanguage.googleapis.com/v1beta/openai", "rpm": 10},
    "groq": {"key": "GROQ_API_KEY", "base": "https://api.groq.com/openai/v1", "rpm": 20},
    "openrouter": {"key": "OPENROUTER_API_KEY", "base": "https://openrouter.ai/api/v1", "rpm": 15},
    "cloudflare": {"key": "CLOUDFLARE_API_TOKEN", "base": "https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/v1", "rpm": 30},
    "openai": {"key": "OPENAI_API_KEY", "base": "https://api.openai.com/v1", "rpm": None},
}
ORDER = ("gemini", "groq", "openrouter", "cloudflare", "openai")
TASKS = tuple(_MODEL_ENV)


def _models(env: Mapping[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for task, names in _MODEL_ENV.items():
        for n in names:
            if env.get(n):
                out[task] = env[n]
                break
    return out


def _backend(name: str, env: Mapping[str, str], models: dict[str, str]) -> ChatCompletionsProvider | None:
    p = PRESETS[name]
    key = env.get(p["key"])
    if not key:
        return None
    override = env.get(f"AI_{name.upper()}_BASE_URL")
    needs_account = "{CLOUDFLARE_ACCOUNT_ID}" in p["base"] and not override
    base = override or p["base"].format_map({"CLOUDFLARE_ACCOUNT_ID": env.get("CLOUDFLARE_ACCOUNT_ID", "")})
    if not base or (needs_account and not env.get("CLOUDFLARE_ACCOUNT_ID")):
        log.error("%s: base URL incomplete (set CLOUDFLARE_ACCOUNT_ID or AI_%s_BASE_URL)", name, name.upper())
        return None
    rpm = env.get(f"AI_{name.upper()}_RPM")
    return ChatCompletionsProvider(name, base, key, models, rpm=float(rpm) if rpm else p["rpm"], structured_mode=env.get(f"AI_{name.upper()}_STRUCTURED", "json_schema"),
                                   timeout_s=float(env.get("AI_REQUEST_TIMEOUT_S", "45")), max_retries=int(env.get("AI_MAX_RETRIES", "2")))


def build_backends_from_env(env: Mapping[str, str] | None = None) -> dict[str, ChatCompletionsProvider]:
    """Every keyed backend, by name (the live-check CLI uses this to list models and test each one on its own)."""
    env = dict(os.environ if env is None else env)
    models = _models(env)
    return {n: b for n in ORDER if (b := _backend(n, env, models)) is not None}


def build_provider_from_env(env: Mapping[str, str] | None = None) -> AIProvider | None:
    """None when no backend has a key (the AI layer then runs in its documented degraded mode)."""
    env = dict(os.environ if env is None else env)
    models = _models(env)
    backends = {n: b for n in ORDER if (b := _backend(n, env, models)) is not None}
    if not backends:
        return None
    first = next(iter(backends))
    routes: dict[str, str] = {t: first for t in TASKS}
    if "groq" in backends:
        routes["transcription"] = "groq"                    # Whisper on Groq is the free speech-to-text path
    for pair in filter(None, (env.get("AI_ROUTES") or "").split(",")):
        task, _, be = pair.partition("=")
        task, be = task.strip(), be.strip()
        if task in TASKS and be in backends:
            routes[task] = be
        else:
            log.error("AI_ROUTES entry %r ignored (unknown task or backend without a key)", pair)
    chosen = {t: backends[b] for t, b in routes.items() if models.get(t)}      # only tasks that have a model id configured are served
    return CompositeProvider(chosen) if chosen else None
