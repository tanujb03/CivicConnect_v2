"""FastAPI wiring: one process-wide gateway, replaceable for tests and for the production (SQL-backed) ports."""
from __future__ import annotations

import threading

from fastapi import Depends

from ai.inference.service import AIService
from backend.core.security import get_current_user

from .memory import DEMO_NOW, DemoCityFactSource, DemoCityRepository, DemoCityToolExecutor, EventStreamAuditSink, MemoryAnalysisStore, MemoryEvidenceResolver, normalize_role
from .providers import build_provider_from_env
from .service import Actor, AIGateway
from .vision import build_from_env as build_vision

_gateway: AIGateway | None = None
_lock = threading.Lock()


def build_ai_service(executor) -> AIService:
    """``AIService.from_env`` loads the local classifier / fusion weights (and an OpenAI Responses provider if configured); a free/alternative backend (Gemini, Groq,
    OpenRouter, Cloudflare, or OpenAI via chat completions) configured through ``providers.build_provider_from_env`` takes precedence."""
    base = AIService.from_env(tool_executor=executor)
    provider = build_provider_from_env()
    if provider is None:
        return base
    return AIService(provider, base.classifier, base.fusion.weights, executor, embedding_weights=base.fusion.embedding_weights)


def build_default_gateway() -> AIGateway:
    """Demo wiring: synthetic demo city + in-memory stores. AI provider/classifier/weights come from the environment (``AIService.from_env``);
    with none configured every endpoint still answers, in the documented degraded mode."""
    repo = DemoCityRepository()
    executor = DemoCityToolExecutor(repo)
    ai = build_ai_service(executor)
    return AIGateway(ai=ai, repo=repo, evidence=MemoryEvidenceResolver(), analyses=MemoryAnalysisStore(), audit=EventStreamAuditSink(),
                     clock=lambda: DEMO_NOW, facts=DemoCityFactSource(executor), vision=build_vision())


def configure_gateway(gateway: AIGateway | None) -> None:
    """Install the production gateway at startup (or a test double); ``None`` resets to lazy default construction."""
    global _gateway
    with _lock:
        _gateway = gateway


def get_gateway() -> AIGateway:
    global _gateway
    if _gateway is None:
        with _lock:
            if _gateway is None:
                _gateway = build_default_gateway()
    return _gateway


def get_actor(current_user: dict = Depends(get_current_user)) -> Actor:
    return Actor(user_id=str(current_user["sub"]), role=normalize_role(current_user.get("role")))
