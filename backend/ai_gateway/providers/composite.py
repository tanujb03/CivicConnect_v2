"""Route each AI task to the backend that is best (or free) for it: e.g. reasoning on Gemini, speech on Groq Whisper, embeddings locally."""
from __future__ import annotations

import logging
from typing import Any, Callable, Mapping, Sequence, TypeVar

from ai.inference.errors import ProviderNotConfigured, ProviderUnavailable
from ai.inference.provider import AIProvider, EmbeddingResult, InputPart, StructuredResult, ToolPlan, ToolSpec, TranscriptResult
from ai.inference.schemas import EvidenceInput

from .cache import ResponseCache, input_hash

log = logging.getLogger("civicconnect.ai.composite")
T = TypeVar("T")
TEXT_TASKS = ("intake", "triage", "resolution", "analytics", "copilot")
TASK_FOR_METHOD = {"embed": "embedding", "transcribe": "transcription", "plan_tools": "copilot"}


class CompositeProvider:
    """``routes`` maps a task name (intake, triage, resolution, analytics, copilot, embedding, transcription) to the provider that serves it."""

    def __init__(self, routes: Mapping[str, AIProvider], fallbacks: Mapping[str, AIProvider] | None = None, cache: ResponseCache | None = None):
        self.cache = cache                              # optional Redis cache of successful primary-model answers (AI_CACHE_ENABLED)
        self.routes = dict(routes)
        self.fallbacks = dict(fallbacks or {})          # task -> a second backend tried ONCE when the primary cannot serve the call (budget spent, cooldown, 429, outage)
        self.name = "composite(" + ",".join(sorted({p.name for p in self.routes.values()})) + ")"

    def __repr__(self) -> str:
        return f"CompositeProvider({ {t: p.name for t, p in self.routes.items()} })"

    def model_for(self, task: str) -> str | None:
        p = self.routes.get(task)
        return p.model_for(task) if p else None

    def _route(self, task: str) -> AIProvider:
        p = self.routes.get(task)
        if p is None:
            raise ProviderNotConfigured(f"no backend routed for task {task!r}")
        return p

    def _with_fallback(self, task: str, capability: str, call: Callable[[AIProvider], T], digest: str, *, has_image: bool = False) -> T:
        primary = self._route(task)
        model = primary.model_for(task) or ""
        if self.cache is not None and (hit := self.cache.get(capability, model, digest)) is not None:
            log.info("AI cache hit: %s model=%s", capability, model)
            return hit
        try:
            result = call(primary)
        except ProviderUnavailable as exc:
            fb = self.fallbacks.get(task)
            if fb is None or has_image:                  # the text fallback models cannot read images: an image request degrades instead
                raise
            log.warning("task %s: %s unavailable (%s); using the fallback %s model %s", task, primary.name, str(exc)[:160], fb.name, fb.model_for(task))
            return call(fb)                              # a fallback answer is never cached under the primary model's key
        if self.cache is not None:
            self.cache.put(capability, model, digest, result)
        return result

    def structured_completion(self, *, task: str, instructions: str, parts: Sequence[InputPart], schema_name: str, json_schema: dict[str, Any]) -> StructuredResult:
        digest = input_hash(instructions=instructions, parts=list(parts), schema_name=schema_name, json_schema=json_schema) if self.cache is not None else ""
        return self._with_fallback(task, f"structured:{task}", lambda p: p.structured_completion(task=task, instructions=instructions, parts=parts, schema_name=schema_name,
                                                                                                  json_schema=json_schema), digest,
                                   has_image=any(getattr(x, "kind", "") == "image" for x in parts))

    def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        return self._with_fallback("embedding", "embed", lambda p: p.embed(texts), input_hash(texts=list(texts)) if self.cache is not None else "", has_image=True)

    def transcribe(self, audio: EvidenceInput, language_hint: str | None = None) -> TranscriptResult:
        digest = input_hash(audio=audio, language_hint=language_hint) if self.cache is not None else ""
        return self._with_fallback("transcription", "transcribe", lambda p: p.transcribe(audio, language_hint), digest, has_image=True)

    def plan_tools(self, *, instructions: str, query: str, tools: Sequence[ToolSpec]) -> ToolPlan:
        digest = input_hash(instructions=instructions, query=query, tools=list(tools)) if self.cache is not None else ""
        return self._with_fallback("copilot", "plan", lambda p: p.plan_tools(instructions=instructions, query=query, tools=tools), digest)
