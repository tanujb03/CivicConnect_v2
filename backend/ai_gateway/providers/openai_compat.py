"""Provider for any OpenAI-COMPATIBLE endpoint: chat completions + embeddings + audio transcriptions.

Covers the free tiers that matter for a student project (Google Gemini's OpenAI-compatible endpoint, Groq, OpenRouter, Cloudflare Workers AI) as well as OpenAI itself,
with the same code and only a different ``base_url`` / key / model ID. Model IDs come exclusively from configuration.

VERIFICATION STATUS: written from the public OpenAI-compatible API shape and covered by mock-transport tests only. It has NOT been run against a live endpoint from
this environment (no keys, egress blocked). Run ``backend/tests/test_free_providers.py`` plus one manual call per backend before relying on it.
Free tiers are rate limited: a per-backend requests-per-minute throttle and ``Retry-After`` aware retries are built in.
"""
from __future__ import annotations

import base64
import json
import logging
import math
import time
from typing import Any, Callable, Sequence

import httpx

from ai.inference.errors import ProviderNotConfigured, ProviderResponseInvalid, ProviderUnavailable
from ai.inference.provider import EmbeddingResult, InputPart, PlannedToolCall, StructuredResult, ToolPlan, ToolSpec, TranscriptResult
from ai.inference.schemas import EvidenceInput

log = logging.getLogger("civicconnect.ai.compat")

_RETRYABLE = {429, 500, 502, 503, 504}
QUOTA_COOLDOWN_S = 60.0          # after a call ends in HTTP 429 the model is not called again for this long (or its Retry-After): requests degrade at once instead of queueing for 15 s
_EMBED_BATCH = 64


class ChatCompletionsProvider:
    def __init__(self, name: str, base_url: str, api_key: str | None, models: dict[str, str], *, rpm: float | None = None, timeout_s: float = 45.0,
                 max_retries: int = 2, structured_mode: str = "json_schema", extra_headers: dict[str, str] | None = None,
                 client: httpx.Client | None = None, sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                 embedding_dim: int | None = None):
        if not api_key:
            raise ProviderNotConfigured(f"{name}: API key is not set")
        if structured_mode not in ("json_schema", "json_object"):
            raise ValueError("structured_mode must be 'json_schema' or 'json_object'")
        self.name = name
        self._base, self._key, self._models = base_url.rstrip("/"), api_key, dict(models)
        self._max_retries, self._mode, self._extra = max_retries, structured_mode, dict(extra_headers or {})
        self._client = client or httpx.Client(timeout=timeout_s)
        self._sleep, self._clock = sleep, clock
        self._min_gap = 60.0 / rpm if rpm else 0.0
        self._last = -1e9
        self._blocked_until: dict[str, float] = {}       # model -> monotonic time until which calls fail fast (quota / rate limit cooldown)
        self._embedding_dim = embedding_dim              # AI_EMBEDDING_DIM: asked from the provider (Matryoshka models), then checked and L2-normalised here

    def __repr__(self) -> str:      # never expose the key
        return f"ChatCompletionsProvider(name={self.name!r}, base_url={self._base!r}, models={self._models})"

    def model_for(self, task: str) -> str | None:
        return self._models.get(task)

    def _require(self, task: str) -> str:
        m = self._models.get(task)
        if not m:
            raise ProviderNotConfigured(f"{self.name}: no model configured for task {task!r} (set the matching AI_*_MODEL variable)")
        return m

    # ------------------------------------------------------------------------------------------ transport
    def _throttle(self) -> None:
        if self._min_gap:
            wait = self._last + self._min_gap - self._clock()
            if wait > 0:
                self._sleep(wait)
            self._last = self._clock()

    def _post(self, path: str, *, json_body: dict | None = None, data: dict | None = None, files: dict | None = None) -> tuple[dict, int]:
        url = self._base + path
        headers = {"Authorization": f"Bearer {self._key}", **self._extra}
        model = str((json_body or data or {}).get("model") or "")
        left = self._blocked_until.get(model, 0.0) - self._clock()
        if left > 0:
            raise ProviderUnavailable(f"{self.name}: {model} is cooling down after HTTP 429 ({int(left) + 1} s left)", status_code=429)
        last: Exception | None = None
        retry_after_seen = 0.0
        t0 = time.monotonic()
        for attempt in range(self._max_retries + 1):
            self._throttle()
            try:
                resp = self._client.post(url, headers=headers, json=json_body, data=data, files=files)
            except httpx.HTTPError as e:
                last = ProviderUnavailable(f"{self.name}: transport error {type(e).__name__}")
            else:
                if resp.status_code < 400:
                    try:
                        return resp.json(), int((time.monotonic() - t0) * 1000)
                    except ValueError as e:
                        raise ProviderResponseInvalid(f"{self.name}: non-JSON body") from e
                last = ProviderUnavailable(f"{self.name}: HTTP {resp.status_code}{self._error_detail(resp)}", status_code=resp.status_code)
                if resp.status_code not in _RETRYABLE:
                    break
                try:
                    retry_after = min(8.0, float(resp.headers.get("retry-after", "0")))
                except ValueError:
                    retry_after = 0.0
                retry_after_seen = max(retry_after_seen, retry_after)
                if attempt < self._max_retries:
                    self._sleep(max(retry_after, 0.5 * (2 ** attempt)))
                continue
            if attempt < self._max_retries:
                self._sleep(0.5 * (2 ** attempt))
        if getattr(last, "status_code", None) == 429:
            self._blocked_until[model] = self._clock() + max(QUOTA_COOLDOWN_S, retry_after_seen)
        log.warning("provider call failed: %s", last)
        raise last  # type: ignore[misc]

    def _error_detail(self, resp: httpx.Response) -> str:
        """`` (provider message)`` from an error body, at most 200 characters, with the API key scrubbed: tells a per-minute from a per-day quota 429 or a rejected model id."""
        try:
            body = resp.json()
            body = body[0] if isinstance(body, list) and body else body
            err = body.get("error") if isinstance(body, dict) else None
            msg = (err.get("message") if isinstance(err, dict) else err) or ""
        except (ValueError, AttributeError):
            msg = ""
        msg = " ".join(str(msg).split()).replace(self._key, "***")
        return f" ({msg[:200]})" if msg else ""

    def list_models(self) -> list[str]:
        """Model ids this key can use (GET /models). Used by the live-check CLI so you can copy valid ids from your own account."""
        self._throttle()
        try:
            resp = self._client.get(self._base + "/models", headers={"Authorization": f"Bearer {self._key}", **self._extra})
        except httpx.HTTPError as e:
            raise ProviderUnavailable(f"{self.name}: transport error {type(e).__name__}") from e
        if resp.status_code >= 400:
            raise ProviderUnavailable(f"{self.name}: HTTP {resp.status_code}", status_code=resp.status_code)
        try:
            rows = resp.json().get("data") or resp.json().get("models") or []
        except ValueError as e:
            raise ProviderResponseInvalid(f"{self.name}: non-JSON model list") from e
        return sorted({str(r.get("id") or r.get("name", "")).removeprefix("models/") for r in rows if isinstance(r, dict)} - {""})

    # ------------------------------------------------------------------------------------------ content
    @staticmethod
    def _user_content(parts: Sequence[InputPart]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for p in parts:
            if p.kind == "text":
                out.append({"type": "text", "text": p.text or ""})
                continue
            ev = p.evidence
            assert ev is not None
            if ev.data is not None:
                url = f"data:{ev.mime_type or 'image/jpeg'};base64,{base64.b64encode(ev.data).decode('ascii')}"
            elif ev.url:
                url = ev.url
            else:
                continue
            out.append({"type": "image_url", "image_url": {"url": url}})
        return out

    @staticmethod
    def _message_text(body: dict) -> str:
        try:
            choice = body["choices"][0]
            msg = choice["message"]
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderResponseInvalid("response had no choices") from e
        if choice.get("finish_reason") in ("content_filter",) or msg.get("refusal"):
            raise ProviderResponseInvalid("provider refused or filtered the request")
        content = msg.get("content")
        if isinstance(content, list):
            content = "".join(c.get("text", "") for c in content if isinstance(c, dict))
        text = (content or "").strip()
        if not text:
            raise ProviderResponseInvalid("provider returned no text")
        return text

    @staticmethod
    def _json_from_text(text: str) -> dict:
        t = text.strip()
        if t.startswith("```"):                                   # some free models fence their JSON
            t = t.strip("`")
            t = t[4:] if t.lower().startswith("json") else t
        start, end = t.find("{"), t.rfind("}")
        if start < 0 or end <= start:
            raise ProviderResponseInvalid("structured output was not a JSON object")
        try:
            data = json.loads(t[start:end + 1])
        except json.JSONDecodeError as e:
            raise ProviderResponseInvalid("structured output was not valid JSON") from e
        if not isinstance(data, dict):
            raise ProviderResponseInvalid("structured output was not a JSON object")
        return data

    # ------------------------------------------------------------------------------------------ protocol
    def structured_completion(self, *, task: str, instructions: str, parts: Sequence[InputPart], schema_name: str, json_schema: dict[str, Any]) -> StructuredResult:
        model = self._require(task)

        def body(mode: str) -> dict:
            system = instructions
            fmt: dict[str, Any]
            if mode == "json_schema":
                fmt = {"type": "json_schema", "json_schema": {"name": schema_name, "schema": json_schema, "strict": True}}
            else:                                                 # JSON mode: the schema travels in the prompt and the service validates the result
                fmt = {"type": "json_object"}
                system = f"{instructions}\n\nReply with ONE JSON object that matches this JSON schema exactly, and nothing else:\n{json.dumps(json_schema)}"
            return {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": self._user_content(parts)}],
                    "response_format": fmt, "temperature": 0}

        try:
            resp, ms = self._post("/chat/completions", json_body=body(self._mode))
        except ProviderUnavailable as e:
            if self._mode == "json_schema" and e.status_code == 400:   # this backend/model does not accept json_schema: retry once in JSON mode
                resp, ms = self._post("/chat/completions", json_body=body("json_object"))
            else:
                raise
        return StructuredResult(data=self._json_from_text(self._message_text(resp)), model=resp.get("model", model), latency_ms=ms, usage=resp.get("usage"))

    def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        model = self._require("embedding")
        vectors: list[list[float]] = []
        total, used = 0, model
        for i in range(0, len(texts), _EMBED_BATCH):
            batch = list(texts[i:i + _EMBED_BATCH])
            body = {"model": model, "input": batch, **({"dimensions": self._embedding_dim} if self._embedding_dim else {})}
            resp, ms = self._post("/embeddings", json_body=body)
            total += ms
            used = resp.get("model", model)
            rows = sorted(resp.get("data", []), key=lambda r: r.get("index", 0))
            if len(rows) != len(batch):
                raise ProviderResponseInvalid("embedding count mismatch")
            vectors.extend([self._checked_vector(r["embedding"]) for r in rows])
        return EmbeddingResult(vectors=vectors, model=used, latency_ms=total)

    def _checked_vector(self, raw: Sequence[float]) -> list[float]:
        """Length must equal AI_EMBEDDING_DIM when set (a truncated or longer vector is a provider/config error, never silently stored); the result is L2-normalised
        because reduced-dimension embeddings of a Matryoshka model are not unit length, and the duplicate search compares by cosine."""
        v = list(map(float, raw))
        if self._embedding_dim and len(v) != self._embedding_dim:
            raise ProviderResponseInvalid(f"{self.name}: embedding has {len(v)} dimensions, AI_EMBEDDING_DIM is {self._embedding_dim}")
        norm = math.sqrt(sum(x * x for x in v))
        if not norm or not math.isfinite(norm):
            raise ProviderResponseInvalid(f"{self.name}: embedding is all zeros or not finite")
        return [x / norm for x in v]

    def transcribe(self, audio: EvidenceInput, language_hint: str | None = None) -> TranscriptResult:
        model = self._require("transcription")
        if audio.data is None:
            raise ProviderResponseInvalid("audio bytes are required for transcription")
        form: dict[str, str] = {"model": model, "response_format": "verbose_json"}      # verbose_json also carries the detected language (OpenAI-style; plain json has none)
        if language_hint and language_hint in {"en", "hi", "mr"}:
            form["language"] = language_hint
        files = {"file": (f"{audio.evidence_id}.webm", audio.data, audio.mime_type or "audio/webm")}
        resp, ms = self._post("/audio/transcriptions", data=form, files=files)
        text = (resp.get("text") or "").strip()
        if not text:
            raise ProviderResponseInvalid("empty transcript")
        return TranscriptResult(text=text, model=model, latency_ms=ms, language=resp.get("language"))

    def plan_tools(self, *, instructions: str, query: str, tools: Sequence[ToolSpec]) -> ToolPlan:
        model = self._require("copilot")
        body = {"model": model, "temperature": 0, "tool_choice": "auto",
                "messages": [{"role": "system", "content": instructions}, {"role": "user", "content": query}],
                "tools": [{"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}} for t in tools]}
        resp, ms = self._post("/chat/completions", json_body=body)
        try:
            msg = resp["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderResponseInvalid("response had no choices") from e
        calls = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            raw = fn.get("arguments", "{}")
            try:
                args = json.loads(raw) if isinstance(raw, str) else dict(raw)
            except (json.JSONDecodeError, TypeError, ValueError):
                args = {"__raw__": str(raw)[:200]}                # rejected visibly by the orchestrator
            calls.append(PlannedToolCall(name=fn.get("name", ""), arguments=args if isinstance(args, dict) else {"__raw__": str(args)[:200]}))
        content = msg.get("content")
        return ToolPlan(calls=calls, model=resp.get("model", model), latency_ms=ms, text=content if isinstance(content, str) and content else None)
