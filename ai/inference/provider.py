"""``AIProvider`` abstraction (system design Section 30).

The rest of CivicConnect depends only on this protocol, never on a vendor SDK
or model name. A different provider can be added by implementing it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, Sequence, runtime_checkable

from .schemas import EvidenceInput


@dataclass
class InputPart:
    """One piece of model input: text or an image (bytes / signed URL)."""

    kind: Literal["text", "image"]
    text: str | None = None
    evidence: EvidenceInput | None = None

    @classmethod
    def of_text(cls, text: str) -> "InputPart":
        return cls("text", text=text)

    @classmethod
    def of_image(cls, evidence: EvidenceInput) -> "InputPart":
        return cls("image", evidence=evidence)


@dataclass
class StructuredResult:
    data: dict[str, Any]
    model: str
    latency_ms: int = 0
    usage: dict[str, Any] | None = None


@dataclass
class EmbeddingResult:
    vectors: list[list[float]]
    model: str
    latency_ms: int = 0

    @property
    def dimension(self) -> int:
        return len(self.vectors[0]) if self.vectors else 0


@dataclass
class TranscriptResult:
    text: str
    model: str
    latency_ms: int = 0
    language: str | None = None


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema


@dataclass
class PlannedToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolPlan:
    calls: list[PlannedToolCall] = field(default_factory=list)
    model: str = ""
    latency_ms: int = 0
    text: str | None = None


@runtime_checkable
class AIProvider(Protocol):
    name: str

    def model_for(self, task: str) -> str | None: ...

    def structured_completion(
        self, *, task: str, instructions: str, parts: Sequence[InputPart],
        schema_name: str, json_schema: dict[str, Any],
    ) -> StructuredResult: ...

    def embed(self, texts: Sequence[str]) -> EmbeddingResult: ...

    def transcribe(self, audio: EvidenceInput, language_hint: str | None = None) -> TranscriptResult: ...

    def plan_tools(
        self, *, instructions: str, query: str, tools: Sequence[ToolSpec]
    ) -> ToolPlan: ...
