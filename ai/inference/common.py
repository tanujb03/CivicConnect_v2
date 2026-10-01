"""Small helpers shared by the capability services."""
from __future__ import annotations

import logging
from typing import Any

from .provider import AIProvider
from .schemas import AIMetadata, MetaSource

log = logging.getLogger("civicconnect.ai")


def clip01(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    if v != v:  # NaN
        return default
    return max(0.0, min(1.0, v))


def log_event(task: str, outcome: str, **fields: Any) -> None:
    """Structured log line. Never pass citizen text, media or secrets here."""
    log.info("ai_task", extra={"task": task, "outcome": outcome, **fields})


def provider_ready(provider: AIProvider | None, task: str) -> bool:
    return provider is not None and bool(provider.model_for(task))


def metadata(task: str, source: MetaSource, *, taxonomy_version: str | None = None,
             provider: AIProvider | None = None, model: str | None = None,
             model_version: str | None = None, prompt_version: str | None = None,
             confidence_basis: str | None = None, fallback_reason: str | None = None,
             latency_ms: int | None = None, input_refs: list[str] | None = None) -> AIMetadata:
    return AIMetadata(
        task_type=task, source=source, provider=provider.name if provider and source.startswith("provider") else None,
        model=model, model_version=model_version, prompt_version=prompt_version,
        taxonomy_version=taxonomy_version, confidence_basis=confidence_basis,
        degraded=fallback_reason is not None, fallback_reason=fallback_reason,
        latency_ms=latency_ms, input_refs=input_refs or [],
    )
