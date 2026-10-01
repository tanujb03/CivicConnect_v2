"""OpenAI REST provider (system design Section 30), implemented over ``httpx``.

IMPORTANT — verification status: request/response shapes below follow the
published Responses / Embeddings / Audio-transcription REST APIs as understood
at implementation time, but **have not been exercised against the live API from
this environment** (no credentials, egress blocked). They are covered by
mock-transport unit tests only. Run ``ai/inference/tests/test_live_provider.py``
with real credentials before relying on this path. Model IDs come exclusively
from configuration.
"""
from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any, Callable, Sequence

import httpx

from ..config import ProviderSettings
from ..errors import ProviderNotConfigured, ProviderResponseInvalid, ProviderUnavailable
from ..provider import EmbeddingResult, InputPart, PlannedToolCall, StructuredResult, ToolPlan, ToolSpec, TranscriptResult
from ..schemas import EvidenceInput

log = logging.getLogger("civicconnect.ai.openai")

_RETRYABLE = {429, 500, 502, 503, 504}
_EMBED_BATCH = 96


class OpenAIProvider:
    name = "openai"

    def __init__(self, settings: ProviderSettings, client: httpx.Client | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        if settings.api_key is None:
            raise ProviderNotConfigured("OPENAI_API_KEY is not set")
        self._settings = settings
        self._client = client or httpx.Client(timeout=settings.timeout_s)
        self._sleep = sleep

    def __repr__(self) -> str:  # never expose the key
        return f"OpenAIProvider(base_url={self._settings.base_url!r}, models={self._settings.models})"

    def model_for(self, task: str) -> str | None:
        return self._settings.model_for(task)

    def _require_model(self, task: str) -> str:
        m = self._settings.model_for(task)
        if not m:
            raise ProviderNotConfigured(f"no model configured for task {task!r} (set the matching AI_*_MODEL variable)")
        return m

    # ------------------------------------------------------------------ #
    def _request(self, path: str, *, json_body: dict | None = None,
                 data: dict | None = None, files: dict | None = None) -> tuple[dict, int]:
        url = self._settings.base_url.rstrip("/") + path
        headers = {"Authorization": f"Bearer {self._settings.api_key.get_secret_value()}"}  # type: ignore[union-attr]
        last: Exception | None = None
        t0 = time.monotonic()
        for attempt in range(self._settings.max_retries + 1):
            try:
                resp = self._client.post(url, headers=headers, json=json_body, data=data, files=files)
            except httpx.HTTPError as e:  # timeouts, connection errors
                last = ProviderUnavailable(f"transport error: {type(e).__name__}")
            else:
                if resp.status_code < 400:
                    try:
                        return resp.json(), int((time.monotonic() - t0) * 1000)
                    except ValueError as e:
                        raise ProviderResponseInvalid("provider returned non-JSON body") from e
                last = ProviderUnavailable(f"HTTP {resp.status_code} from provider", status_code=resp.status_code)
                if resp.status_code not in _RETRYABLE:
                    break
            if attempt < self._settings.max_retries:
                self._sleep(0.5 * (2 ** attempt))
        log.warning("provider call failed", extra={"path": path, "error": str(last)})
        raise last  # type: ignore[misc]

    # ------------------------------------------------------------------ #
    @staticmethod
    def _content(parts: Sequence[InputPart]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for p in parts:
            if p.kind == "text":
                out.append({"type": "input_text", "text": p.text or ""})
            else:
                ev = p.evidence
                assert ev is not None
                if ev.data is not None:
                    mime = ev.mime_type or "image/jpeg"
                    url = f"data:{mime};base64,{base64.b64encode(ev.data).decode('ascii')}"
                elif ev.url:
                    url = ev.url
                else:
                    continue  # transcript-only evidence has no image payload
                out.append({"type": "input_image", "image_url": url})
        return out

    @staticmethod
    def _output_text(body: dict) -> str:
        if body.get("status") == "incomplete":
            raise ProviderResponseInvalid("provider response incomplete")
        chunks: list[str] = []
        for item in body.get("output", []):
            if item.get("type") != "message":
                continue
            for c in item.get("content", []):
                if c.get("type") == "refusal":
                    raise ProviderResponseInvalid("provider refused the request")
                if c.get("type") == "output_text":
                    chunks.append(c.get("text", ""))
        text = "".join(chunks).strip()
        if not text:
            raise ProviderResponseInvalid("provider returned no text output")
        return text

    def structured_completion(self, *, task: str, instructions: str, parts: Sequence[InputPart],
                              schema_name: str, json_schema: dict[str, Any]) -> StructuredResult:
        model = self._require_model(task)
        body = {
            "model": model,
            "instructions": instructions,
            "input": [{"role": "user", "content": self._content(parts)}],
            "text": {"format": {"type": "json_schema", "name": schema_name, "schema": json_schema, "strict": True}},
            "store": False,  # citizen evidence should not be retained by the provider by default
        }
        resp, ms = self._request("/responses", json_body=body)
        text = self._output_text(resp)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ProviderResponseInvalid("structured output was not valid JSON") from e
        if not isinstance(data, dict):
            raise ProviderResponseInvalid("structured output was not a JSON object")
        return StructuredResult(data=data, model=resp.get("model", model), latency_ms=ms, usage=resp.get("usage"))

    def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        model = self._require_model("embedding")
        vectors: list[list[float]] = []
        total_ms = 0
        used_model = model
        for i in range(0, len(texts), _EMBED_BATCH):
            batch = list(texts[i : i + _EMBED_BATCH])
            resp, ms = self._request("/embeddings", json_body={"model": model, "input": batch})
            total_ms += ms
            used_model = resp.get("model", model)
            rows = sorted(resp.get("data", []), key=lambda r: r.get("index", 0))
            if len(rows) != len(batch):
                raise ProviderResponseInvalid("embedding count mismatch")
            vectors.extend([list(map(float, r["embedding"])) for r in rows])
        return EmbeddingResult(vectors=vectors, model=used_model, latency_ms=total_ms)

    def transcribe(self, audio: EvidenceInput, language_hint: str | None = None) -> TranscriptResult:
        model = self._require_model("transcription")
        if audio.data is None:
            raise ProviderResponseInvalid("audio bytes are required for transcription")
        form: dict[str, str] = {"model": model}
        if language_hint and language_hint in {"en", "hi", "mr"}:
            form["language"] = language_hint
        files = {"file": (f"{audio.evidence_id}.audio", audio.data, audio.mime_type or "audio/webm")}
        resp, ms = self._request("/audio/transcriptions", data=form, files=files)
        text = (resp.get("text") or "").strip()
        if not text:
            raise ProviderResponseInvalid("empty transcript")
        return TranscriptResult(text=text, model=model, latency_ms=ms, language=resp.get("language"))

    def plan_tools(self, *, instructions: str, query: str, tools: Sequence[ToolSpec]) -> ToolPlan:
        model = self._require_model("copilot")
        body = {
            "model": model,
            "instructions": instructions,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": query}]}],
            "tools": [{"type": "function", "name": t.name, "description": t.description,
                       "parameters": t.parameters} for t in tools],
            "tool_choice": "auto",
            "store": False,
        }
        resp, ms = self._request("/responses", json_body=body)
        calls: list[PlannedToolCall] = []
        text_chunks: list[str] = []
        for item in resp.get("output", []):
            if item.get("type") == "function_call":
                raw = item.get("arguments", "{}")
                try:
                    args = json.loads(raw) if isinstance(raw, str) else dict(raw)
                except (json.JSONDecodeError, TypeError, ValueError):
                    args = {"__raw__": str(raw)[:200]}  # rejected visibly by the orchestrator
                calls.append(PlannedToolCall(name=item.get("name", ""), arguments=args))
            elif item.get("type") == "message":
                for c in item.get("content", []):
                    if c.get("type") == "output_text":
                        text_chunks.append(c.get("text", ""))
        return ToolPlan(calls=calls, model=resp.get("model", model), latency_ms=ms,
                        text="".join(text_chunks) or None)
