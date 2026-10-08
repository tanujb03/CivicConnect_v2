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
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Sequence

import httpx

from ai.inference.errors import ProviderNotConfigured, ProviderResponseInvalid, ProviderUnavailable
from ai.inference.provider import EmbeddingResult, InputPart, PlannedToolCall, StructuredResult, ToolPlan, ToolSpec, TranscriptResult
from ai.inference.schemas import EvidenceInput

from .. import timing
from .budget import BudgetSpent, ModelBudgets

log = logging.getLogger("civicconnect.ai.compat")

_RETRYABLE = {429, 500, 502, 503, 504}
QUOTA_COOLDOWN_S = 60.0          # default cooldown after a call ends in HTTP 429 when the provider names no delay: requests degrade at once instead of queueing for 15 s
UNKNOWN_RESET_COOLDOWN_S = 3600.0   # a per-day quota whose reset time cannot be computed (no tzdata): one hour
MAX_COOLDOWN_S = 26 * 3600.0
DEFAULT_DEADLINE_S = 20.0        # AI_PROVIDER_TIMEOUT_S: the overall deadline of ONE provider call (HTTP attempts + retries + throttle + budget waits)


class ProviderTimeout(ProviderUnavailable):
    """The overall deadline of one provider call passed (no more attempts were started). Not a quota error: it never starts the 429 cooldown."""
    timed_out = True


def _estimate_tokens(body: dict | None) -> int:
    """A cheap upper-ish estimate of the input tokens of a request body (text only; an image counts as 300): 4 characters per token for ASCII, 2 for other scripts."""
    def text_tokens(s: str) -> int:
        return -(-len(s) // (4 if s.isascii() else 2))

    total = 0
    for item in (body or {}).get("input", []) if isinstance((body or {}).get("input"), list) else []:
        total += text_tokens(str(item)) + 1
    for msg in (body or {}).get("messages", []) or []:
        content = msg.get("content") if isinstance(msg, dict) else None
        if isinstance(content, str):
            total += text_tokens(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    total += 300 if part.get("type") == "image_url" else text_tokens(str(part.get("text") or ""))
    return total


def _seconds(value: object) -> float | None:
    """Google duration strings (``"23s"``, ``"0.5s"``) and plain numbers -> seconds."""
    try:
        return float(str(value).rstrip("s"))
    except (TypeError, ValueError):
        return None


def parse_quota_error(body: object, retry_after_header: str | None = None) -> dict:
    """What a provider 429 says about WHICH limit was hit: ``message``, ``status``, ``quota_id``, ``quota_metric``, ``quota_model``, ``quota_value``, ``retry_delay_s``.
    Reads Google's ``QuotaFailure`` / ``RetryInfo`` error details (Gemini) and falls back to the ``Retry-After`` header; every field is optional."""
    body = body[0] if isinstance(body, list) and body else body
    err = body.get("error") if isinstance(body, dict) else None
    out: dict = {}
    if isinstance(err, dict):
        out["message"] = " ".join(str(err.get("message") or "").split())
        out["status"] = err.get("status")
        for d in err.get("details") or []:
            if not isinstance(d, dict):
                continue
            kind = str(d.get("@type", ""))
            if kind.endswith("QuotaFailure"):
                v = next((x for x in d.get("violations") or [] if isinstance(x, dict)), {})
                out.update(quota_id=v.get("quotaId"), quota_metric=v.get("quotaMetric"), quota_value=v.get("quotaValue"), quota_model=(v.get("quotaDimensions") or {}).get("model"))
            elif kind.endswith("RetryInfo"):
                out["retry_delay_s"] = _seconds(d.get("retryDelay"))
    if out.get("retry_delay_s") is None and retry_after_header:
        out["retry_delay_s"] = _seconds(retry_after_header)
    return {k: v for k, v in out.items() if v not in (None, "")}


def next_daily_reset_seconds(now: datetime | None = None) -> float:
    """Seconds until the next midnight in America/Los_Angeles (Gemini API daily quotas reset then); 1 hour when the time zone database is not installed."""
    try:
        from zoneinfo import ZoneInfo
        pt = ZoneInfo("America/Los_Angeles")
    except Exception:
        return UNKNOWN_RESET_COOLDOWN_S
    here = (now or datetime.now(timezone.utc)).astimezone(pt)
    midnight = (here + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(60.0, (midnight - here).total_seconds())


def cooldown_seconds(quota: dict) -> float:
    """How long to stop calling a model after a 429: a per-day quota until the daily reset, otherwise the provider's retry delay (+1 s), otherwise ``QUOTA_COOLDOWN_S``."""
    quota_id = str(quota.get("quota_id") or "").lower()
    delay = quota.get("retry_delay_s")
    if "perday" in quota_id or "per_day" in quota_id or "daily" in quota_id:
        return min(MAX_COOLDOWN_S, next_daily_reset_seconds())
    if delay:
        return min(MAX_COOLDOWN_S, max(float(delay) + 1.0, 5.0))
    return QUOTA_COOLDOWN_S
_EMBED_BATCH = 64


class ChatCompletionsProvider:
    def __init__(self, name: str, base_url: str, api_key: str | None, models: dict[str, str], *, rpm: float | None = None, timeout_s: float = 45.0,
                 max_retries: int = 2, deadline_s: float | None = DEFAULT_DEADLINE_S, structured_mode: str = "json_schema", extra_headers: dict[str, str] | None = None,
                 client: httpx.Client | None = None, sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                 embedding_dim: int | None = None, budgets: ModelBudgets | None = None):
        if not api_key:
            raise ProviderNotConfigured(f"{name}: API key is not set")
        if structured_mode not in ("json_schema", "json_object"):
            raise ValueError("structured_mode must be 'json_schema' or 'json_object'")
        self.name = name
        self._base, self._key, self._models = base_url.rstrip("/"), api_key, dict(models)
        self._max_retries, self._mode, self._extra = max_retries, structured_mode, dict(extra_headers or {})
        self._client = client or httpx.Client(timeout=timeout_s)
        self._timeout_s = timeout_s                      # per HTTP attempt (AI_REQUEST_TIMEOUT_S); each attempt gets min(this, time left of the deadline)
        self._deadline_s = deadline_s if deadline_s and deadline_s > 0 else None     # per provider call (AI_PROVIDER_TIMEOUT_S); None = no deadline
        self._sleep, self._clock = sleep, clock
        self._min_gap = 60.0 / rpm if rpm else 0.0
        self._last = -1e9
        self._blocked_until: dict[str, float] = {}       # model -> monotonic time until which calls fail fast (quota / rate limit cooldown)
        self._cooling: set[str] = set()                  # models whose cooldown start has been logged (the end is logged once, lazily)
        self._budgets = budgets                          # per-model rpm / rpd / tpm budgets (None = unlimited)
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
    def _throttle(self, remaining: float | None = None, limit: float | None = None) -> None:
        if self._min_gap:
            wait = self._last + self._min_gap - self._clock()
            if wait > 0:
                if remaining is not None and wait >= remaining:
                    raise self._deadline_error(f"the {wait:.0f} s rate-limit spacing does not fit in the remaining {max(remaining, 0):.0f} s", limit)
                self._sleep(wait)
            self._last = self._clock()

    def _deadline_error(self, detail: str, limit: float | None = None) -> ProviderTimeout:
        return ProviderTimeout(f"{self.name}: deadline of {limit or self._deadline_s:g} s exceeded ({detail})")

    def _pause(self, seconds: float, deadline: float | None) -> bool:
        """Sleep before a retry; False (no sleep) when the pause would not leave time for another attempt before the deadline."""
        if deadline is not None and seconds >= deadline - self._clock():
            return False
        self._sleep(seconds)
        return True

    @staticmethod
    def _outcome(exc: BaseException | None) -> str:
        if exc is None:
            return "ok"
        if isinstance(exc, BudgetSpent):
            return "budget"
        if getattr(exc, "timed_out", False):
            return "timeout"
        if isinstance(exc, ProviderUnavailable):
            return f"http_{exc.status_code}" if exc.status_code else "transport_error"
        return "invalid" if isinstance(exc, ProviderResponseInvalid) else "error"

    def _post(self, path: str, *, json_body: dict | None = None, data: dict | None = None, files: dict | None = None, task: str = "") -> tuple[dict, int]:
        """One provider call: HTTP attempts with retries under the overall deadline. Logs ONE INFO line (task, backend, model, attempts, provider_ms = time inside the HTTP calls,
        waited_ms = throttle + budget waits + retry sleeps, total_ms, outcome) and adds the same figures to the request's ``timing`` accumulator."""
        model = str((json_body or data or {}).get("model") or "")
        task = task or path.strip("/").split("/")[-1]
        if timing.spent():                                       # the request's total provider budget (AI_REQUEST_DEADLINE_S) is used up: no new call
            log.info("ai provider call: task=%s backend=%s model=%s attempts=0 provider_ms=0 waited_ms=0 total_ms=0 outcome=request_deadline", task, self.name, model)
            raise ProviderTimeout(f"{self.name}: request deadline of {timing.deadline_s():g} s reached; call not started")
        left = self._blocked_until.get(model, 0.0) - self._clock()
        if left > 0:
            log.info("ai provider call: task=%s backend=%s model=%s attempts=0 provider_ms=0 waited_ms=0 total_ms=0 outcome=cooldown", task, self.name, model)
            raise ProviderUnavailable(f"{self.name}: {model} is cooling down after HTTP 429 ({int(left) + 1} s left)", status_code=429)
        t0, stat = self._clock(), {"provider": 0.0, "attempts": 0}
        error: BaseException | None = None
        try:
            return self._send(path, model, json_body, data, files, t0, stat)
        except BaseException as exc:
            error = exc
            raise
        finally:
            total_ms = int((self._clock() - t0) * 1000)
            provider_ms = int(stat["provider"] * 1000)
            waited_ms = max(0, total_ms - provider_ms)
            timing.add(provider_ms, waited_ms)
            timing.spent()                                       # logs "ai request deadline reached" once when this call used up the request budget
            log.info("ai provider call: task=%s backend=%s model=%s attempts=%d provider_ms=%d waited_ms=%d total_ms=%d outcome=%s", task, self.name, model, stat["attempts"],
                     provider_ms, waited_ms, total_ms, self._outcome(error))

    def _send(self, path: str, model: str, json_body: dict | None, data: dict | None, files: dict | None, t0: float, stat: dict) -> tuple[dict, int]:
        url = self._base + path
        headers = {"Authorization": f"Bearer {self._key}", **self._extra}
        if model in self._cooling:
            self._cooling.discard(model)
            log.info("provider cooldown ended: %s model=%s; calling it again", self.name, model)
        limit, req_left = self._deadline_s, timing.remaining()   # this call's deadline: AI_PROVIDER_TIMEOUT_S, capped by what is left of the request budget
        if req_left is not None:
            limit = min(limit, req_left) if limit else req_left
        deadline = t0 + limit if limit else None
        last: Exception | None = None
        quota: dict = {}
        stopped = False                                          # True: a retry was dropped because the deadline would pass first
        attempt = 0
        tokens = _estimate_tokens(json_body) if self._budgets else 0
        units = len(json_body["input"]) if json_body and isinstance(json_body.get("input"), list) else 1       # inputs of an embeddings call: counted one by one for per_input models
        for attempt in range(self._max_retries + 1):
            if self._budgets:
                self._budgets.acquire(model, tokens, units)             # may wait a few seconds (its own limit, AI_BUDGET_MAX_WAIT_S); raises BudgetSpent (no request sent) when spent
            self._throttle(None if deadline is None else deadline - self._clock(), limit)
            remaining = None if deadline is None else deadline - self._clock()
            if remaining is not None and remaining <= 0:
                raise self._deadline_error(f"no time left for attempt {attempt + 1}" + (f"; last: {last}" if last else ""), limit)
            stat["attempts"] += 1
            p0 = self._clock()
            try:
                resp = self._client.post(url, headers=headers, json=json_body, data=data, files=files,
                                         timeout=self._timeout_s if remaining is None else min(self._timeout_s, remaining))
            except httpx.HTTPError as e:
                stat["provider"] += self._clock() - p0
                last = ProviderUnavailable(f"{self.name}: transport error {type(e).__name__}")
                if isinstance(e, httpx.TimeoutException):
                    last.timed_out = True                        # type: ignore[attr-defined]
                if deadline is not None and self._clock() >= deadline:
                    raise self._deadline_error(f"attempt {attempt + 1} timed out; last: {last}", limit) from e
            else:
                stat["provider"] += self._clock() - p0
                if resp.status_code < 400:
                    try:
                        return resp.json(), int((self._clock() - t0) * 1000)
                    except ValueError as e:
                        raise ProviderResponseInvalid(f"{self.name}: non-JSON body") from e
                last = ProviderUnavailable(f"{self.name}: HTTP {resp.status_code}{self._error_detail(resp)}", status_code=resp.status_code)
                if resp.status_code == 429:
                    quota = self._quota(resp)
                    last.quota = quota                                  # type: ignore[attr-defined]
                if resp.status_code not in _RETRYABLE:
                    break
                try:
                    retry_after = min(8.0, float(resp.headers.get("retry-after", "0")))
                except ValueError:
                    retry_after = 0.0
                if attempt < self._max_retries and not self._pause(max(retry_after, 0.5 * (2 ** attempt)), deadline):
                    stopped = True
                    break
                continue
            if attempt < self._max_retries and not self._pause(0.5 * (2 ** attempt), deadline):
                stopped = True
                break
        if getattr(last, "status_code", None) == 429:
            secs = cooldown_seconds(quota)
            self._blocked_until[model] = self._clock() + secs
            if model not in self._cooling:
                self._cooling.add(model)
                until = (datetime.now(timezone.utc) + timedelta(seconds=secs)).isoformat(timespec="seconds")
                log.warning("provider cooldown started: %s model=%s for %d s (until %s UTC) quota_id=%s metric=%s retry_delay_s=%s", self.name, model, int(secs), until,
                            quota.get("quota_id"), quota.get("quota_metric"), quota.get("retry_delay_s"))
        elif stopped:                                            # a timeout is not a quota error: no cooldown, only the log line
            err = self._deadline_error(f"no time left to retry after attempt {attempt + 1}; last: {last}", limit)
            log.warning("provider call failed: %s", err)
            raise err
        log.warning("provider call failed: %s", last)
        raise last  # type: ignore[misc]

    def _quota(self, resp: httpx.Response) -> dict:
        try:
            body = resp.json()
        except ValueError:
            body = None
        return parse_quota_error(body, resp.headers.get("retry-after"))

    def _error_detail(self, resp: httpx.Response) -> str:
        """`` (provider message) [quota_id=... quota_metric=... quota_model=... quota_value=... retry_in=...s]`` from an error body: the message at most 200 characters, the API key
        scrubbed. Tells a per-minute from a per-day quota 429, or a rejected model id, from a bad request."""
        try:
            body = resp.json()
            body = body[0] if isinstance(body, list) and body else body
            err = body.get("error") if isinstance(body, dict) else None
            msg = (err.get("message") if isinstance(err, dict) else err) or ""
        except (ValueError, AttributeError):
            msg = ""
        msg = " ".join(str(msg).split()).replace(self._key, "***")
        text = f" ({msg[:200]})" if msg else ""
        if resp.status_code == 429:
            q = self._quota(resp)
            parts = [f"{k}={q[k]}" for k in ("quota_id", "quota_metric", "quota_model", "quota_value") if k in q]
            if "retry_delay_s" in q:
                parts.append(f"retry_in={q['retry_delay_s']:g}s")
            if parts:
                text += " [" + " ".join(parts).replace(self._key, "***") + "]"
        return text

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
            resp, ms = self._post("/chat/completions", json_body=body(self._mode), task=task)
        except ProviderUnavailable as e:
            if self._mode == "json_schema" and e.status_code == 400:   # this backend/model does not accept json_schema: retry once in JSON mode
                resp, ms = self._post("/chat/completions", json_body=body("json_object"), task=task)
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
            resp, ms = self._post("/embeddings", json_body=body, task="embedding")
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
        resp, ms = self._post("/audio/transcriptions", data=form, files=files, task="transcription")
        text = (resp.get("text") or "").strip()
        if not text:
            raise ProviderResponseInvalid("empty transcript")
        return TranscriptResult(text=text, model=model, latency_ms=ms, language=resp.get("language"))

    def plan_tools(self, *, instructions: str, query: str, tools: Sequence[ToolSpec]) -> ToolPlan:
        model = self._require("copilot")
        body = {"model": model, "temperature": 0, "tool_choice": "auto",
                "messages": [{"role": "system", "content": instructions}, {"role": "user", "content": query}],
                "tools": [{"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}} for t in tools]}
        resp, ms = self._post("/chat/completions", json_body=body, task="copilot")
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
