"""Route each AI task to the backend that is best (or free) for it: e.g. reasoning on Gemini, speech on Groq Whisper, embeddings locally."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from ai.inference.errors import ProviderNotConfigured
from ai.inference.provider import AIProvider, EmbeddingResult, InputPart, StructuredResult, ToolPlan, ToolSpec, TranscriptResult
from ai.inference.schemas import EvidenceInput

TASK_FOR_METHOD = {"embed": "embedding", "transcribe": "transcription", "plan_tools": "copilot"}


class CompositeProvider:
    """``routes`` maps a task name (intake, triage, resolution, analytics, copilot, embedding, transcription) to the provider that serves it."""

    def __init__(self, routes: Mapping[str, AIProvider]):
        self.routes = dict(routes)
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

    def structured_completion(self, *, task: str, instructions: str, parts: Sequence[InputPart], schema_name: str, json_schema: dict[str, Any]) -> StructuredResult:
        return self._route(task).structured_completion(task=task, instructions=instructions, parts=parts, schema_name=schema_name, json_schema=json_schema)

    def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        return self._route("embedding").embed(texts)

    def transcribe(self, audio: EvidenceInput, language_hint: str | None = None) -> TranscriptResult:
        return self._route("transcription").transcribe(audio, language_hint)

    def plan_tools(self, *, instructions: str, query: str, tools: Sequence[ToolSpec]) -> ToolPlan:
        return self._route("copilot").plan_tools(instructions=instructions, query=query, tools=tools)
