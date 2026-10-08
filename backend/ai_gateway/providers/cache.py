"""Optional Redis cache of AI capability responses, so demo reruns are repeatable without spending quota.

Off by default (``AI_CACHE_ENABLED=false``); TTL ``AI_CACHE_TTL_S`` (default 24 h). Key: capability + model + SHA-256 of the whole input (instructions, text, image bytes, schema,
tools, audio bytes, language hint). Only SUCCESSFUL answers of the primary model are stored: an exception never reaches this code, and the composite skips the cache when a
fallback model answered. No Redis => no caching (every call goes to the provider).

PRIVACY: the cached value is the model's answer to citizen-supplied text, images and audio, kept in Redis for the TTL. Keep this OFF for real citizen data; it is meant for
rehearsals on the synthetic demo city.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
from typing import Any, Callable

from ai.inference.provider import EmbeddingResult, PlannedToolCall, StructuredResult, ToolPlan, TranscriptResult

log = logging.getLogger("civicconnect.ai.cache")

PREFIX = "civic:aicache"


def _canon(value: Any) -> Any:
    """JSON-able, order-stable form of an input; bytes become their digest so images and audio are hashed, never stored."""
    if isinstance(value, (bytes, bytearray)):
        return {"sha256": hashlib.sha256(value).hexdigest()}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _canon(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if hasattr(value, "model_fields"):                                  # pydantic model (EvidenceInput): its `data` field is excluded from dumps, so add it explicitly
        out = {k: _canon(getattr(value, k)) for k in type(value).model_fields}
        return out
    if isinstance(value, dict):
        return {str(k): _canon(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_canon(v) for v in value]
    return value if isinstance(value, (str, int, float, bool)) or value is None else str(value)


def input_hash(**inputs: Any) -> str:
    return hashlib.sha256(json.dumps(_canon(inputs), sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


class ResponseCache:
    def __init__(self, *, ttl_s: int = 86400, redis_getter: Callable[[], Any] | None = None) -> None:
        self.ttl_s = ttl_s
        self._redis_getter = redis_getter

    @classmethod
    def from_env(cls, env) -> "ResponseCache | None":
        if str(env.get("AI_CACHE_ENABLED", "false")).strip().lower() not in ("1", "true", "yes", "on"):
            return None
        return cls(ttl_s=int(env.get("AI_CACHE_TTL_S", "86400")))

    def _redis(self):
        if self._redis_getter is not None:
            return self._redis_getter()
        from backend.events import publisher
        return publisher.get_redis()

    @staticmethod
    def key(capability: str, model: str, digest: str) -> str:
        return f"{PREFIX}:{capability}:{model}:{digest}"

    def get(self, capability: str, model: str, digest: str) -> Any | None:
        r = self._redis()
        if r is None:
            return None
        try:
            raw = r.get(self.key(capability, model, digest))
            return _revive(capability, json.loads(raw)) if raw else None
        except Exception as exc:                                        # a cache problem must never fail an AI call
            log.debug("AI cache read skipped (%s)", type(exc).__name__)
            return None

    def put(self, capability: str, model: str, digest: str, result: Any) -> None:
        r = self._redis()
        if r is None:
            return
        try:
            r.set(self.key(capability, model, digest), json.dumps(dataclasses.asdict(result), ensure_ascii=False), ex=self.ttl_s)
        except Exception as exc:
            log.debug("AI cache write skipped (%s)", type(exc).__name__)


def _revive(capability: str, data: dict) -> Any:
    kind = capability.split(":", 1)[0]
    if kind == "structured":
        return StructuredResult(**data)
    if kind == "embed":
        return EmbeddingResult(**data)
    if kind == "transcribe":
        return TranscriptResult(**data)
    if kind == "plan":
        return ToolPlan(calls=[PlannedToolCall(**c) for c in data.get("calls", [])], model=data.get("model", ""), latency_ms=data.get("latency_ms", 0), text=data.get("text"))
    raise ValueError(capability)
