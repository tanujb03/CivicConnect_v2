"""Compare Groq text models as the possible Gemini fallback on the REAL intake pipeline (schema validity, label agreement, latency, token use vs the 8K TPM limit).

    python -m scripts.dev.compare_fallback_models --models <model-id-1> <model-id-2> --dry-run
    python -m scripts.dev.compare_fallback_models --models <model-id-1> <model-id-2>

The model ids are always given on the command line (never defaulted, never stored). Rows: the gold file ``ai/training/gold/gold_llm_authored_claude_v1.csv`` (provenance
``llm_authored_claude``: written by an LLM, NOT human gold, NOT real citizen text); the FIXED rule takes the first two rows of ``hi``, ``mr`` and ``hi-Latn`` after sorting by a
content id (``g-`` + 8 hex of sha1(language|label|text)), so reruns and both models see identical rows. The prompt, JSON schema and validation are the production ones
(``AIService.analyze_intake`` over ``CompositeProvider({"intake": ...})``); no images. Real calls only without ``--dry-run``: at most 12 rows (+ one structured-mode probe per
model), no retries, paced to stay under ``--token-budget`` (7000) tokens in any rolling 60 s window and the provider's requests/min; a 429 (or any provider HTTP error) stops that
model with the exact provider message. Keys come from ``load_env_file()`` and are never printed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable, Sequence

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ai.inference.errors import ProviderResponseInvalid, ProviderUnavailable  # noqa: E402
from ai.inference.schemas import IntakeRequest  # noqa: E402

GOLD = ROOT / "ai" / "training" / "gold" / "gold_llm_authored_claude_v1.csv"
OUT = Path(r"D:\ml-cache\tmp\fallback_compare.json")
LANGS = ("hi", "mr", "hi-Latn")
PER_LANG = 2
TPM_LIMIT = 8000                 # the owner's reading of Groq's per-model limit (2026-10-08)
DEFAULT_TOKEN_BUDGET = 7000      # our own ceiling in any rolling window
WINDOW_S = 60.0
MAX_ROW_CALLS = 12
MAX_HTTP = 14                    # 12 row calls + at most one json_schema -> json_object probe per model
PRINT_TEXT = 80


# ------------------------------------------------------------------------------------------ pure logic
def row_id(row: dict) -> str:
    """Stable content id of a gold row (the CSV has no id column)."""
    return "g-" + hashlib.sha1(f"{row['language']}|{row['label_id']}|{row['text']}".encode("utf-8")).hexdigest()[:8]


def pick_rows(rows: Sequence[dict], langs: Sequence[str] = LANGS, per_lang: int = PER_LANG) -> list[dict]:
    """The fixed rule: per language the first ``per_lang`` rows after sorting by id; each picked row gets its ``id``, ``category`` and ``subcategory``."""
    out: list[dict] = []
    for lang in langs:
        mine = sorted(({**r, "id": row_id(r)} for r in rows if r.get("language") == lang), key=lambda r: r["id"])
        for r in mine[:per_lang]:
            cat, _, sub = r["label_id"].partition("/")
            out.append({**r, "category": cat, "subcategory": sub})
    return out


def clip(text: str, n: int = PRINT_TEXT) -> str:
    one = " ".join(text.split())
    return one if len(one) <= n else one[: n - 3] + "..."


def projected_calls_per_minute(avg_total_tokens: float | None, tpm: int = TPM_LIMIT) -> int | None:
    """floor(tpm / average total tokens per call); None without a measurement."""
    return int(tpm // avg_total_tokens) if avg_total_tokens and avg_total_tokens > 0 else None


def usage_numbers(usage: dict | None) -> dict[str, int | None]:
    u = usage if isinstance(usage, dict) else {}
    p, c = u.get("prompt_tokens"), u.get("completion_tokens")
    t = u.get("total_tokens")
    if t is None and isinstance(p, int) and isinstance(c, int):
        t = p + c
    return {"prompt_tokens": p if isinstance(p, int) else None, "completion_tokens": c if isinstance(c, int) else None, "total_tokens": t if isinstance(t, int) else None}


def estimate_tokens(*texts: str) -> int:
    """Rough input estimate used only for the first call of a model (4 chars per token for ASCII, 2 otherwise) plus 400 for the answer."""
    return 400 + sum(-(-len(s) // (4 if s.isascii() else 2)) for s in texts)


class TokenWindow:
    """Rolling token window built from the ``usage`` the provider returned: ``wait_needed(predicted)`` is how long to sleep so that ``predicted`` more tokens keep the
    window sum at or under the budget."""

    def __init__(self, budget: int = DEFAULT_TOKEN_BUDGET, window_s: float = WINDOW_S, clock: Callable[[], float] = time.monotonic):
        self.budget, self.window_s, self._clock = budget, window_s, clock
        self._events: deque[tuple[float, int]] = deque()

    def _trim(self) -> None:
        now = self._clock()
        while self._events and now - self._events[0][0] >= self.window_s:
            self._events.popleft()

    def used(self) -> int:
        self._trim()
        return sum(n for _, n in self._events)

    def record(self, tokens: int) -> None:
        self._events.append((self._clock(), max(0, int(tokens))))

    def wait_needed(self, predicted: int) -> float:
        """Seconds until enough old events leave the window for ``predicted`` more tokens to fit (0 when they fit now; if they can never fit, until the window is empty)."""
        self._trim()
        total, now = sum(n for _, n in self._events) + predicted, self._clock()
        if total <= self.budget:
            return 0.0
        for t, n in self._events:
            total -= n
            if total <= self.budget:
                return max(0.0, t + self.window_s - now)
        return max(0.0, self._events[-1][0] + self.window_s - now) if self._events else 0.0


def summarise(model: str, calls: list[dict], *, tpm: int = TPM_LIMIT) -> dict:
    """Per-model figures from the per-row records (each has ok/schema_valid/cat_ok/sub_ok/provider_ms/total_tokens/error)."""
    ran = [c for c in calls if c.get("status") != "skipped"]
    answered = [c for c in ran if c.get("answered")]
    totals = [c["total_tokens"] for c in ran if c.get("total_tokens") is not None]
    avg = sum(totals) / len(totals) if totals else None
    ms = [c["provider_ms"] for c in answered if c.get("provider_ms") is not None]
    modes = [m for c in ran for m in c.get("modes_worked", [])]
    errors = [c["error"] for c in ran if c.get("error")]
    return {
        "model": model, "rows_planned": len(calls), "rows_called": len(ran), "schema_valid": sum(bool(c.get("schema_valid")) for c in ran),
        "category_agree": sum(bool(c.get("cat_ok")) for c in ran), "subcategory_agree": sum(bool(c.get("sub_ok")) for c in ran),
        "median_provider_ms": int(statistics.median(ms)) if ms else None, "avg_total_tokens": round(avg, 1) if avg is not None else None,
        "avg_prompt_tokens": round(statistics.fmean([c["prompt_tokens"] for c in ran if c.get("prompt_tokens") is not None]), 1) if any(c.get("prompt_tokens") is not None for c in ran) else None,
        "avg_completion_tokens": (round(statistics.fmean([c["completion_tokens"] for c in ran if c.get("completion_tokens") is not None]), 1)
                                  if any(c.get("completion_tokens") is not None for c in ran) else None),
        "max_total_tokens": max(totals) if totals else None, "any_call_over_tpm": any(t > tpm for t in totals),
        "projected_calls_per_min_at_tpm": projected_calls_per_minute(avg, tpm), "structured_mode": ("+".join(sorted(set(modes))) if modes else None),
        "json_schema_rejected": any(c.get("json_schema_rejected") for c in ran), "errors": errors[:3],
    }


# ------------------------------------------------------------------------------------------ the real run
class Recorder:
    """Wraps the provider routed for 'intake': remembers the last StructuredResult / error of each call (the service itself swallows errors into its fallback path) and logs every
    HTTP request the adapter makes (structured mode, status, message) by wrapping its ``_post``."""

    def __init__(self, inner: Any, max_http: int = MAX_HTTP):
        self.inner, self.name = inner, inner.name
        self.requests: list[dict] = []
        self.http_total = 0
        self.max_http = max_http
        self.last_result: Any = None
        self.last_error: BaseException | None = None
        orig = inner._post

        def post(path: str, **kw: Any):
            body = kw.get("json_body") or {}
            mode = ((body.get("response_format") or {}).get("type")) or "none"
            if self.http_total >= self.max_http:
                raise ProviderUnavailable("compare script: HTTP request cap reached; call not sent")
            self.http_total += 1
            rec = {"mode": mode, "status": None, "message": None}
            self.requests.append(rec)
            try:
                out = orig(path, **kw)
            except ProviderUnavailable as e:
                rec.update(status=e.status_code, message=str(e), quota=getattr(e, "quota", None))
                raise
            except Exception as e:
                rec.update(status="invalid", message=f"{type(e).__name__}: {e}")
                raise
            rec["status"] = 200
            return out

        inner._post = post

    def model_for(self, task: str) -> str | None:
        return self.inner.model_for(task)

    def structured_completion(self, **kw: Any):
        self.last_result, self.last_error = None, None
        try:
            self.last_result = self.inner.structured_completion(**kw)
            return self.last_result
        except BaseException as e:
            self.last_error = e
            raise

    def __getattr__(self, name: str) -> Any:      # embed / transcribe / plan_tools etc. are never used here
        return getattr(self.inner, name)


def classify_call(rec: Recorder, resp: Any, before: int, timing_ms: int, gold: dict) -> dict:
    """Turn one finished pipeline call into the per-call record (no secrets)."""
    reqs = rec.requests[before:]
    res, err = rec.last_result, rec.last_error
    meta = resp.ai_metadata
    schema_valid = meta.source == "provider" and not meta.degraded
    nums = usage_numbers(res.usage if res is not None else None)
    p = resp.proposal
    rejected = any(r["mode"] == "json_schema" and r["status"] == 400 for r in reqs)
    out: dict[str, Any] = {
        "id": gold["id"], "language": gold["language"], "gold": gold["label_id"], "text": gold["text"],
        "status": "ok" if schema_valid else "degraded", "answered": res is not None or isinstance(err, ProviderResponseInvalid),
        "schema_valid": schema_valid, "pred": f"{p.category}/{p.subcategory}" if schema_valid else None,
        "raw_pred": f"{res.data.get('category')}/{res.data.get('subcategory')}" if res is not None else None,
        "cat_ok": schema_valid and p.category == gold["category"], "sub_ok": schema_valid and p.subcategory == gold["subcategory"],
        "confidence": resp.confidence if schema_valid else None, "warnings": [getattr(w, "code", str(w)) for w in resp.warnings] if hasattr(resp, "warnings") else [],
        "provider_ms": timing_ms, **nums, "http_requests": [{k: v for k, v in r.items() if k in ("mode", "status")} for r in reqs],
        "modes_worked": sorted({r["mode"] for r in reqs if r["status"] in (200, "invalid")}), "json_schema_rejected": rejected,
        "fallback_reason": meta.fallback_reason, "error": None,
    }
    if err is not None:
        out["error"] = f"{type(err).__name__}: {err}"[:400]
        if isinstance(err, ProviderUnavailable):
            out.update(status="provider_error", http_status=err.status_code, quota=getattr(err, "quota", None))
    return out


def run_model(model: str, rows: list[dict], make_provider: Callable[[str], Any], *, window: TokenWindow, sleep: Callable[[float], None] = time.sleep,
              log: Callable[[str], None] = print) -> list[dict]:
    """Real intake calls for one model over ``rows``; stops at the first provider HTTP error (429, 400/404 model rejected, ...) and marks the rest skipped."""
    from ai.inference import prompts
    from ai.inference.config import load_taxonomy
    from ai.inference.service import AIService
    from backend.ai_gateway import timing
    from backend.ai_gateway.providers.composite import CompositeProvider

    inner = make_provider(model)
    rec = Recorder(inner)
    service = AIService(CompositeProvider({"intake": rec}), taxonomy=load_taxonomy())
    base_est = estimate_tokens(prompts.intake_instructions(service.taxonomy), json.dumps(prompts.intake_schema(service.taxonomy)))
    out: list[dict] = []
    seen: list[int] = []
    stopped = False
    for g in rows:
        if stopped or len([c for c in out if c["status"] != "skipped"]) >= MAX_ROW_CALLS:
            out.append({"id": g["id"], "language": g["language"], "gold": g["label_id"], "text": g["text"], "status": "skipped"})
            continue
        predicted = max(seen) if seen else base_est + estimate_tokens(g["text"])
        wait = window.wait_needed(predicted)
        if wait > 0:
            log(f"  [{model}] pacing: sleeping {wait:.1f}s (window {window.used()} + ~{predicted} tokens > {window.budget})")
            sleep(wait + 0.5)
        before = len(rec.requests)
        timing.start(None)
        resp = service.analyze_intake(IntakeRequest(text=g["text"]))
        snap = timing.snapshot()
        call = classify_call(rec, resp, before, snap["provider_ms"], g)
        out.append(call)
        if call.get("total_tokens") is not None:
            window.record(call["total_tokens"])
            seen.append(call["total_tokens"])
        if call.get("json_schema_rejected") and "json_object" in call["modes_worked"]:
            inner._mode = "json_object"                         # the adapter retries json_object per call; stay there to avoid a second request per row
        if call["status"] == "provider_error":
            stopped = True
            log(f"  [{model}] STOPPED at {g['id']}: {call['error']}")
    return out


def make_groq_provider(model: str):
    from backend.ai_gateway.providers.factory import _backend
    env = {**os.environ, "AI_MAX_RETRIES": "0", "AI_MODEL_LIMITS": "off", "AI_PROVIDER_TIMEOUT_S": "60"}
    p = _backend("groq", env, {"intake": model})
    if p is None:
        raise SystemExit("GROQ_API_KEY is not set (put it in the gitignored .env; names only: python scripts/dev/env_names.py)")
    return p


def table(summaries: list[dict]) -> str:
    cols = [("model", "model"), ("rows_called", "rows"), ("schema_valid", "valid"), ("category_agree", "cat"), ("subcategory_agree", "sub"), ("median_provider_ms", "med_ms"),
            ("avg_total_tokens", "avg_tok"), ("max_total_tokens", "max_tok"), ("projected_calls_per_min_at_tpm", "calls/min@8K"), ("structured_mode", "mode")]
    rows = [[str(s.get(k) if s.get(k) is not None else "-") for k, _ in cols] for s in summaries]
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, (_, h) in enumerate(cols)]
    line = lambda cells: "  ".join(c.ljust(w) for c, w in zip(cells, widths))  # noqa: E731
    return "\n".join([line([h for _, h in cols]), line(["-" * w for w in widths]), *(line(r) for r in rows)])


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--models", nargs=2, required=True, metavar="MODEL_ID", help="the two Groq model ids to compare (required, never defaulted)")
    ap.add_argument("--dry-run", action="store_true", help="print the chosen rows, models and planned call count; make no call")
    ap.add_argument("--gold", type=Path, default=GOLD)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--token-budget", type=int, default=DEFAULT_TOKEN_BUDGET)
    a = ap.parse_args(argv)

    from ai.training.src.text_corpus.build import load_gold
    gold, _ = load_gold(a.gold)
    rows = pick_rows(gold)
    planned = len(rows) * len(a.models)
    print(f"gold file: {a.gold.name} (provenance llm_authored_claude: LLM-written, NOT human gold)")
    print(f"models: {', '.join(a.models)}   rows per model: {len(rows)}   planned real calls: {planned} (cap {MAX_ROW_CALLS}, no retries)   token budget/60s: {a.token_budget}")
    for g in rows:
        print(f"  {g['id']}  {g['language']:<8} {g['label_id']:<34} {clip(g['text'])}")
    if a.dry_run:
        print("dry run: no call made")
        return 0
    if planned > MAX_ROW_CALLS:
        raise SystemExit(f"planned calls {planned} exceed the cap {MAX_ROW_CALLS}")

    from backend.ai_gateway.envfile import load_env_file
    load_env_file()
    results: dict[str, Any] = {"gold_file": a.gold.name, "provenance": "llm_authored_claude", "tpm_limit": TPM_LIMIT, "token_budget": a.token_budget, "models": {}}
    summaries = []
    for model in a.models:
        print(f"running {model} ...")
        calls = run_model(model, rows, make_groq_provider, window=TokenWindow(a.token_budget))
        s = summarise(model, calls)
        results["models"][model] = {"summary": s, "calls": calls}
        summaries.append(s)
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(table(summaries))
    for s in summaries:
        for e in s["errors"]:
            print(f"error [{s['model']}]: {e}")
        print(f"[{s['model']}] schema-valid {s['schema_valid']}/{s['rows_called']}, json_schema rejected: {s['json_schema_rejected']}, any call over {TPM_LIMIT} tokens: {s['any_call_over_tpm']}, "
              f"avg prompt/completion tokens {s['avg_prompt_tokens']}/{s['avg_completion_tokens']}")
    print(f"raw results: {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
