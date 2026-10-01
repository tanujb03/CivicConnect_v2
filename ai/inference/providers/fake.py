"""Deterministic in-process provider for tests, demos and backend unit tests.

Scripted responses are returned per task; an ``Exception`` instance in the
script is raised instead, which makes failure/fallback paths easy to test.
Embeddings are hashed character-trigram vectors, so textually similar inputs
get genuinely higher cosine similarity (useful for fusion tests) without any
external model. **These are not real model outputs.**
"""
from __future__ import annotations

import hashlib
import math
from typing import Any, Sequence

from ..errors import ProviderResponseInvalid
from ..local.featurizer import char_wb_ngrams, normalize_text
from ..provider import EmbeddingResult, InputPart, PlannedToolCall, StructuredResult, ToolPlan, ToolSpec, TranscriptResult
from ..schemas import EvidenceInput


class FakeProvider:
    name = "fake"

    def __init__(self, structured: dict[str, Any] | None = None, transcript: str | Exception = "fake transcript",
                 tool_plan: list[PlannedToolCall] | Exception | None = None, dim: int = 64,
                 models: dict[str, str] | None = None):
        self.structured = structured or {}
        self._transcript = transcript
        self._tool_plan = tool_plan if tool_plan is not None else []
        self.dim = dim
        self.models = models or {}
        self.calls: list[tuple[str, Any]] = []

    def model_for(self, task: str) -> str | None:
        return self.models.get(task, f"fake-{task}")

    def structured_completion(self, *, task: str, instructions: str, parts: Sequence[InputPart],
                              schema_name: str, json_schema: dict[str, Any]) -> StructuredResult:
        self.calls.append(("structured", {"task": task, "schema": schema_name, "parts": list(parts)}))
        item = self.structured.get(task)
        if item is None:
            raise ProviderResponseInvalid(f"FakeProvider has no scripted response for task {task!r}")
        if isinstance(item, Exception):
            raise item
        data = item(parts) if callable(item) else item
        return StructuredResult(data=dict(data), model=f"fake-{task}", latency_ms=1)

    def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        self.calls.append(("embed", list(texts)))
        return EmbeddingResult(vectors=[self._vec(t) for t in texts], model="fake-embedding", latency_ms=1)

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for g in char_wb_ngrams(normalize_text(text), (3, 3)):
            h = int(hashlib.md5(g.encode("utf-8")).hexdigest(), 16)
            v[h % self.dim] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def transcribe(self, audio: EvidenceInput, language_hint: str | None = None) -> TranscriptResult:
        self.calls.append(("transcribe", audio.evidence_id))
        if isinstance(self._transcript, Exception):
            raise self._transcript
        return TranscriptResult(text=self._transcript, model="fake-transcription", latency_ms=1)

    def plan_tools(self, *, instructions: str, query: str, tools: Sequence[ToolSpec]) -> ToolPlan:
        self.calls.append(("plan_tools", query))
        if isinstance(self._tool_plan, Exception):
            raise self._tool_plan
        return ToolPlan(calls=list(self._tool_plan), model="fake-copilot", latency_ms=1)
