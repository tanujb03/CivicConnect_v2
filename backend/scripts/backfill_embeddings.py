"""Embed the cases that have no embedding yet, in batches, inside the free-tier quota of the embedding model.

    python -m backend.scripts.backfill_embeddings --dry-run                         # counts, tokens, minutes, requests; NO provider call, NO write, no API key needed
    python -m backend.scripts.backfill_embeddings --limit 10 --batch-size 10        # the PROBE (<= 100 inputs, no flag needed): compare its daily-counter delta with AI Studio's usage page
    python -m backend.scripts.backfill_embeddings --counting per-batch|per-input    # a run of more than 100 inputs: say what AI Studio's usage page showed for the probe

Rules (there is deliberately NO --force):
* only cases WITHOUT a ``case_embeddings`` row are selected, and a vector that appeared meanwhile is kept (checked before the call and inside the saving transaction);
* idempotent and resumable: every vector is committed, a rerun picks up only what is still missing and makes 0 requests when nothing is;
* one attempt per batch: ``AI_MAX_RETRIES=0`` is set before the provider is built (a retry multiplies requests); a rerun is the retry;
* pacing: at most 80 requests/min and the configured tokens/min (25,000 at most; the provider budget allows 100 / 30,000): this script composes ``AI_MODEL_LIMITS`` for the
  embedding model id (daily limit kept from the table) and ``AI_BUDGET_MAX_WAIT_S=65`` BEFORE the provider is built, so minute budgets are waited for, not refused. The provider
  is always wrapped in a request counter, also when a local embedder is configured and fails over to it;
* each text is cut at 8000 characters (reported as truncated); empty or over-long texts never use up ``--limit``;
* a batch the provider rejects for itself (HTTP 400, an invalid answer) is bisected, at most 20 extra requests per run, to isolate the bad rows: those are skipped for this run and
  their case ids printed; HTTP 429 / a spent budget stops at once (exit 2, no bisecting); any other failure (outage, 5xx) stops (exit 3);
* ``--daily-ceiling N`` / ``--assume-used-today M``: a hard stop for the day's requests (M = what AI Studio shows before the run).
* ``--counting``: the daily quota may count a batch call as 1 request (``per-batch``) or every input as 1 (``per-input``); this cannot be known offline. A run of more than
  100 inputs is refused (exit 64) until you state which one AI Studio's usage page showed for the probe. ``per-input`` keeps inputs per minute <= 80 and inputs per run <=
  (daily limit - used today), and ``--max-requests`` then counts inputs. A model without a daily limit in the table is refused for more than 100 inputs.

Exit codes: 0 done (or nothing to do), 2 stopped for quota (429, spent budget, --max-requests / daily room), 3 stopped for another failure (or every row failed), 64 bad
arguments or a refused run, 130 interrupted.
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, MutableMapping

from sqlalchemy import func, select

from ai.inference.common import provider_ready
from ai.inference.errors import ProviderResponseInvalid
from backend.ai_gateway.envfile import load_env_file
from backend.ai_gateway.providers.budget import BudgetSpent, Limits, ModelBudgets, parse_limits
from backend.ai_gateway.providers.factory import ORDER, PRESETS, _models
from backend.ai_gateway.providers.openai_compat import _EMBED_BATCH, _estimate_tokens
from backend.ai_gateway.service import SYSTEM_ACTOR
from backend.ai_gateway.sql import SqlCaseRepository
from backend.db.session import session_scope
from backend.models import CaseEmbedding, CivicCase

PACE_RPM, PACE_TPM = 80, 25_000                  # our own ceiling, below the provider's 100 requests/min and 30,000 tokens/min
MAX_WAIT_S = "65"                                # a full minute budget is waited for (a window is 60 s), not refused
DEFAULT_BATCH, MAX_BATCH, DEFAULT_MAX_REQUESTS = 50, 100, 800
MAX_CHARS = 8000                                 # per input, about 2K tokens
PROBE_INPUTS = 100                               # a run of at most this many inputs needs no --counting
BISECT_EXTRA = 20                                # extra requests per run to isolate rejected rows
COUNTING = ("per-batch", "per-input")
EXIT_OK, EXIT_QUOTA, EXIT_FAIL, EXIT_USAGE, EXIT_INTERRUPTED = 0, 2, 3, 64, 130
PROBE_CMD = "python -m backend.scripts.backfill_embeddings --limit 10 --batch-size 10"


@dataclass
class Options:
    dry_run: bool = False
    limit: int | None = None
    batch_size: int = DEFAULT_BATCH
    max_requests: int = DEFAULT_MAX_REQUESTS
    counting: str | None = None
    daily_ceiling: int | None = None             # hard stop: never let the day's embedding requests pass this (the owner keeps a reserve for runtime and calibration)
    assume_used_today: int = 0                   # what Google AI Studio showed before the run (requests from other processes or earlier runs the local counter never saw)


@dataclass
class Plan:
    missing_total: int = 0                       # all cases without an embedding row
    examined: int = 0                            # rows looked at (all of them, or up to the point where --limit eligible rows were found)
    empty: list[str] = field(default_factory=list)       # no text: never sent (and, having no row, examined again by every run)
    too_long: list[str] = field(default_factory=list)    # one text alone above the token ceiling even after the cut: never sent
    truncated: list[str] = field(default_factory=list)   # cut at MAX_CHARS
    gone: int = 0                                # selected but deleted meanwhile
    batches: list[list[str]] = field(default_factory=list)
    batch_tokens: list[int] = field(default_factory=list)
    tokens: dict[str, int] = field(default_factory=dict)

    @property
    def rows(self) -> int:
        return sum(len(b) for b in self.batches)

    @property
    def http_requests(self) -> int:
        """Assumption A: one HTTP embeddings call (<= 64 inputs) counts as one request."""
        return sum(math.ceil(len(b) / _EMBED_BATCH) for b in self.batches)


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------- selection
def select_missing() -> tuple[int, list[str]]:
    """(count, ids oldest first) of ALL cases without an embedding row. The LEFT JOIN is the ONLY selection rule; ``--limit`` is applied later, to eligible rows."""
    with session_scope() as db:
        base = select(CivicCase.id).outerjoin(CaseEmbedding, CaseEmbedding.case_id == CivicCase.id).where(CaseEmbedding.case_id.is_(None))
        total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
        return int(total), list(db.execute(base.order_by(CivicCase.created_at, CivicCase.id)).scalars())


def build_plan(repo: Any, ids: list[str], batch_size: int, token_cap: int = PACE_TPM, limit: int | None = None, max_chars: int = MAX_CHARS) -> Plan:
    """Texts exactly as ``embed_case`` sees them (``repo.get_case(...).text``, cut at ``max_chars``), then greedy batches of at most ``batch_size`` rows and ``token_cap``
    estimated tokens. Empty and over-long rows are set aside and do not count towards ``limit``; the plan stops once ``limit`` eligible rows are batched."""
    plan = Plan()
    cur: list[str] = []
    cur_t = eligible = 0
    for cid in ids:
        if limit and eligible >= limit:
            break
        plan.examined += 1
        case = repo.get_case(cid)
        if case is None:
            plan.gone += 1
            continue
        text = (case.text or "").strip()
        if not text:
            plan.empty.append(cid)
            continue
        if len(text) > max_chars:
            text = text[:max_chars]
            plan.truncated.append(cid)
        t = _estimate_tokens({"input": [text]})
        if t > token_cap:
            plan.too_long.append(cid)
            continue
        if cur and (len(cur) >= batch_size or cur_t + t > token_cap):
            plan.batches.append(cur)
            plan.batch_tokens.append(cur_t)
            cur, cur_t = [], 0
        cur.append(cid)
        cur_t += t
        plan.tokens[cid] = t
        eligible += 1
    if cur:
        plan.batches.append(cur)
        plan.batch_tokens.append(cur_t)
    return plan


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------- pacing
def configured_model(env: Mapping[str, str]) -> str | None:
    """The embedding model id from the environment (the same lookup the provider factory uses), or None."""
    return _models(env).get("embedding")


def pace_limits(env: Mapping[str, str], model: str | None) -> Limits:
    """Our ceiling for ``model``: rpm and tpm capped at 80 / 25,000 (lower configured values are kept), the daily limit from the table or ``AI_MODEL_LIMITS``."""
    spec = (env.get("AI_MODEL_LIMITS") or "").strip()
    lim = parse_limits(None if spec.lower() == "off" else spec).get(model or "", Limits()) if model else Limits()
    return Limits(min(lim.rpm or PACE_RPM, PACE_RPM), lim.rpd, min(lim.tpm or PACE_TPM, PACE_TPM))


def apply_pacing(env: MutableMapping[str, str], model: str) -> Limits:
    """Writes the override that the provider factory reads (so it must run BEFORE the provider is built); returns the effective limits."""
    lim = pace_limits(env, model)
    spec = (env.get("AI_MODEL_LIMITS") or "").strip()
    env["AI_MODEL_LIMITS"] = ",".join(x for x in ("" if spec.lower() == "off" else spec, f"{model}={lim.rpm}/{lim.rpd or '-'}/{lim.tpm}") if x)
    env["AI_BUDGET_MAX_WAIT_S"] = MAX_WAIT_S
    return lim


def apply_run_env(env: MutableMapping[str, str], model: str | None) -> None:
    """Everything the provider factory must see BEFORE it builds the provider: one attempt per request (a retry would silently multiply requests) and the pacing."""
    env["AI_MAX_RETRIES"] = "0"
    if model:
        apply_pacing(env, model)


class InputPacer:
    """Keeps the inputs sent in any 60 s window <= ``per_minute`` (``--counting per-input``: the provider may count every input as a request)."""

    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep) -> None:
        self.per_minute, self._clock, self._sleep, self._win = per_minute, clock, sleep, deque()

    def wait(self, n: int) -> None:
        while True:
            now = self._clock()
            while self._win and self._win[0][0] <= now - 60.0:
                self._win.popleft()
            if sum(k for _, k in self._win) + n <= self.per_minute or not self._win:
                self._win.append((now, n))
                return
            self._sleep(self._win[0][0] + 60.0 - now + 0.05)


def embedding_backend(env: Mapping[str, str]) -> str:
    """Which backend name the embedding route uses (the daily counter's key): AI_ROUTES, else the first keyed backend, else gemini (a dry run needs no key)."""
    for pair in (env.get("AI_ROUTES") or "").split(","):
        task, _, be = pair.partition("=")
        if task.strip() == "embedding" and be.strip() in PRESETS:
            return be.strip()
    return next((n for n in ORDER if env.get(PRESETS[n]["key"])), "gemini")


def local_counter(env: Mapping[str, str], model: str) -> tuple[int, str, str]:
    """(requests the daily counter holds for today, where it came from, backend name). Reads Redis (the same counter the API process increments) or the process memory."""
    backend = embedding_backend(env)
    b = ModelBudgets({}, provider=backend, tz_name=env.get("AI_QUOTA_TZ", "America/Los_Angeles"))
    where = "Redis" if b._redis() is not None else "process memory only (Redis unreachable: this shows 0 for a fresh process)"
    return b.used_today(model), where, backend


def budgets_of(provider: Any) -> ModelBudgets | None:
    """The per-model budgets behind the embedding route (through the counting proxy and the composite), or None."""
    p = getattr(provider, "_inner", provider)
    p = (getattr(p, "routes", None) or {}).get("embedding", p)
    return getattr(p, "_budgets", None)


class CountingProvider:
    """Delegates to the real provider and counts the ``embed`` calls this script makes and the HTTP requests behind them (the adapter splits at 64 inputs)."""

    def __init__(self, inner: Any) -> None:
        self._inner, self.embed_calls, self.http_requests = inner, 0, 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def embed(self, texts):
        self.embed_calls += 1
        try:
            res = self._inner.embed(texts)
        except Exception:
            self.http_requests += 1                                # the failing request; with AI_MAX_RETRIES=0 nothing was repeated (the daily counter delta is the exact count)
            raise
        self.http_requests += max(1, math.ceil(len(texts) / _EMBED_BATCH))
        return res


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------- reports
def _stats(xs: list[int]) -> str:
    return f"min {min(xs)} / avg {sum(xs) / len(xs):.0f} / max {max(xs)}" if xs else "n/a"


def dry_run_lines(plan: Plan, opts: Options, model: str | None, pace: Limits, used: tuple[int, str, str] | None) -> list[str]:
    """The dry-run report: nothing here talks to a provider."""
    tokens = sum(plan.batch_tokens)
    a, b = plan.http_requests, plan.rows
    by_tok, by_req = tokens / pace.tpm, a / pace.rpm
    L = ["backfill_embeddings DRY RUN: no provider call, no write",
         f"model: {model or '<not configured>'}   (set AI_EMBEDDING_MODEL; a dry run needs no API key)",
         f"cases without an embedding row: {plan.missing_total}" + (f" (--limit {opts.limit} takes the oldest {opts.limit} ELIGIBLE rows; {plan.examined} examined)" if opts.limit else ""),
         f"  with empty text (skipped, never sent): {len(plan.empty)}" + (f"; unreadable/deleted: {plan.gone}" if plan.gone else "")
         + (f"; too long for one request: {len(plan.too_long)}" if plan.too_long else "") + (f"; texts cut at {MAX_CHARS} characters: {len(plan.truncated)}" if plan.truncated else ""),
         f"  to embed: {plan.rows} rows in {len(plan.batches)} batches (batch size {opts.batch_size})",
         f"estimated tokens: total {tokens}; per batch {_stats(plan.batch_tokens)}",
         f"minimum time at {pace.rpm} requests/min and {pace.tpm} tokens/min: {max(by_tok, by_req):.1f} min (tokens {by_tok:.1f} min, requests {by_req:.1f} min)"]
    limit = pace.rpd if model else None
    left = f"{limit} requests/day" if limit else "unknown (no model configured or no daily limit in the table)"
    used_s = "unknown" if used is None else f"{used[0]} used today (daily counter from {used[1]}; key backend {used[2]})"
    L += [f"requests needed, assumption A (one HTTP embeddings call = 1 request; the adapter sends <= {_EMBED_BATCH} inputs per call): {a}",
          f"requests needed, assumption B (every input counts as 1 request): {b}",
          f"daily limit: {left}; {used_s}"]
    if limit and used is not None:
        room = limit - used[0]
        L.append(f"room today: {room}; A needs {a} ({'fits' if a <= room else 'DOES NOT FIT'}), B needs {b} ({'fits' if b <= room else 'DOES NOT FIT'})"
                 + f"; this run is capped at --max-requests {opts.max_requests}")
    L += ["UNVERIFIED: whether Google counts a batch call as 1 request (A) or each input as 1 (B) cannot be known offline. The local daily counter assumes A.",
          f"Under B the per-minute limit would bind too (>= {b / pace.rpm:.1f} min); a per-minute 429 stops the run with exit 2 and a rerun continues.",
          f"To settle it run the probe: {PROBE_CMD}  and compare 'daily counter delta' with AI Studio's usage page (1 = per-batch, 10 = per-input).",
          f"A run of more than {PROBE_INPUTS} inputs is refused until you pass --counting per-batch or --counting per-input."]
    return L


def final_lines(r: dict[str, Any]) -> list[str]:
    if r["counter_delta"] is not None:
        delta = f"{r['counter_delta']} (before {r['counter_before']}, after {r['counter_after']})"
    else:
        delta = r["counter_note"] or "n/a (no budget counter for this route)"
    L = [f"backfill_embeddings report: {r['stop_reason'] or 'finished'}",
         f"model: {r['model'] or '<not configured>'}; route: {r['route']}; counting: {r['counting'] or 'probe (<= 100 inputs)'}",
         f"rows selected: {r['selected']}; rows embedded: {r['embedded']} (via local embedder: {r['embedded_local']}, via provider: {r['embedded_provider']}); "
         f"rows skipped (empty text): {r['skipped_empty']}; already embedded/kept: {r['skipped_existing']}; too long: {r['too_long']}; failed to store: {r['failed']}",
         f"batches: {r['batches_done']} of {r['batches_planned']} planned (+{r['bisect_calls']} bisecting calls)",
         f"requests used: {r['embed_calls']} provider.embed calls = {r['http_requests']} HTTP requests (counted per 64-input call; AI_MAX_RETRIES=0, nothing repeated)",
         f"daily counter delta (compare with Google AI Studio's usage page): {delta}",
         f"estimated tokens sent: {r['tokens']}; elapsed: {r['elapsed_s']:.1f} s"]
    if r.get("daily_ceiling") is not None or r.get("assumed_used_today"):
        sent = r["counter_delta"] if r["counter_delta"] is not None else r["embedded_provider"]
        L.append(f"daily ceiling: {r.get('daily_ceiling')}; assumed used before this run (AI Studio): {r.get('assumed_used_today')}; EXPECT about {(r.get('assumed_used_today') or 0) + sent} "
                 f"requests/day in AI Studio after this run (every input counts as one request)")
    if r["local_fallbacks"]:
        L.append(f"the local embedder failed in {r['local_fallbacks']} batch(es) and the provider embedded them (counted and paced)")
    if r["truncated"]:
        L.append(f"texts cut at {MAX_CHARS} characters: {len(r['truncated'])}: {', '.join(r['truncated'][:20])}" + (" ..." if len(r["truncated"]) > 20 else ""))
    if r["bad_rows"]:
        L.append(f"rows the provider rejected, SKIPPED for this run: {len(r['bad_rows'])}")
        L += [f"  {cid}: {why}" for cid, why in list(r["bad_rows"].items())[:50]]
    L.append(f"exit code: {r['exit_code']}")
    return L


def classify(exc: Exception) -> tuple[int, str]:
    """(exit code, why) for a failed batch: quota -> 2 (rerun later), anything else -> 3 (look at it first)."""
    name, msg = type(exc).__name__, " ".join(str(exc).split())[:200]
    if isinstance(exc, BudgetSpent) or getattr(exc, "status_code", None) == 429:
        return EXIT_QUOTA, f"quota: {name}: {msg}. What was stored is kept; rerun later (the daily quota resets at midnight Pacific) to embed only what is still missing"
    return EXIT_FAIL, f"{name}: {msg}. The failed batch was not stored; nothing was retried"


def isolatable(exc: Exception) -> bool:
    """A failure of THIS batch's content (HTTP 400/413/422, an invalid answer) that bisecting can isolate; outages, 5xx and 429 are not."""
    return isinstance(exc, ProviderResponseInvalid) or (not isinstance(exc, BudgetSpent) and getattr(exc, "status_code", None) in (400, 413, 422))


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------- run
def _default_gateway():
    from backend.ai_gateway.sql import build_sql_gateway
    return build_sql_gateway()


def execute(opts: Options, *, gateway_factory: Callable[[], Any] | None = None, environ: MutableMapping[str, str] | None = None,
            used_today: Callable[[Mapping[str, str], str], tuple[int, str, str]] | None = None, out: Callable[[str], None] = print,
            clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep) -> tuple[int, dict[str, Any]]:
    """Returns (exit code, report). ``gateway_factory`` / ``environ`` / ``used_today`` / ``clock`` / ``sleep`` are injectable for tests."""
    t0 = time.monotonic()
    if environ is None:
        load_env_file()
    env: MutableMapping[str, str] = os.environ if environ is None else environ
    rep: dict[str, Any] = {"selected": 0, "embedded": 0, "embedded_local": 0, "embedded_provider": 0, "local_fallbacks": 0, "skipped_empty": 0, "skipped_existing": 0, "too_long": 0,
                           "failed": 0, "batches_done": 0, "batches_planned": 0, "bisect_calls": 0, "embed_calls": 0, "http_requests": 0, "tokens": 0, "counter_before": None,
                           "counter_after": None, "counter_delta": None, "counter_note": None, "model": None, "route": "none", "counting": opts.counting, "truncated": [],
                           "bad_rows": {}, "stop_reason": None, "exit_code": EXIT_OK, "elapsed_s": 0.0}

    def done(code: int, reason: str | None = None) -> tuple[int, dict[str, Any]]:
        rep.update(exit_code=code, stop_reason=reason or rep["stop_reason"], elapsed_s=time.monotonic() - t0)
        if not opts.dry_run:
            for line in final_lines(rep):
                out(line)
        return code, rep

    try:
        model = configured_model(env)
        pace = pace_limits(env, model)
    except ValueError as e:
        return done(EXIT_FAIL, f"STOP: bad AI_MODEL_LIMITS: {e}")
    rep["model"] = model
    total, ids = select_missing()
    eff_batch = min(opts.batch_size, pace.rpm) if opts.counting == "per-input" else opts.batch_size
    plan = build_plan(SqlCaseRepository(), ids, eff_batch, pace.tpm, opts.limit)
    plan.missing_total = total
    rep.update(selected=plan.rows, skipped_empty=len(plan.empty), too_long=len(plan.too_long), batches_planned=len(plan.batches), truncated=list(plan.truncated))
    if opts.dry_run:
        used = None
        if model:
            try:
                used = (used_today or local_counter)(env, model)
            except Exception as e:                                          # noqa: BLE001  (the counter is informational)
                out(f"(daily counter unreadable: {type(e).__name__})")
        for line in dry_run_lines(plan, opts, model, pace, used):
            out(line)
        return done(EXIT_OK, "dry run")
    if not plan.batches:
        return done(EXIT_OK, "nothing to embed (every case has an embedding or no text); 0 requests made")
    apply_run_env(env, model)                                               # retries off + pacing, BEFORE the provider is built
    try:
        gw = (gateway_factory or _default_gateway)()
    except Exception as e:                                                  # noqa: BLE001
        return done(EXIT_FAIL, f"STOP: the AI gateway could not be built ({type(e).__name__})")
    provider, local = gw.ai.provider, gw.embedder is not None
    use_provider = provider_ready(provider, "embedding")
    if not local and not use_provider:
        return done(EXIT_FAIL, "STOP: no embedding provider/model configured (set GEMINI_API_KEY and AI_EMBEDDING_MODEL, or AI_EMBED_ONNX_PATH); nothing was sent")
    model_id = provider.model_for("embedding") if use_provider else None
    lim = pace_limits(env, model_id) if model_id else None
    if use_provider and plan.rows > PROBE_INPUTS:
        if opts.counting is None:
            return done(EXIT_USAGE, f"REFUSED: this run would embed {plan.rows} inputs (more than {PROBE_INPUTS}) and it is not known whether the daily quota counts a batch or every input. "
                                    f"Run the probe first: {PROBE_CMD}; compare its 'daily counter delta' with AI Studio's usage page (1 = per-batch, 10 = per-input), then rerun with "
                                    f"--counting per-batch or --counting per-input")
        if lim is None or lim.rpd is None:
            return done(EXIT_USAGE, f"REFUSED: {model_id} has no daily limit (rpd) in the budget table or AI_MODEL_LIMITS, so there is no daily cap to respect and the daily counter "
                                    f"means nothing; add 'model=rpm/rpd/tpm' to AI_MODEL_LIMITS or run at most {PROBE_INPUTS} inputs")
    counting = CountingProvider(provider) if use_provider else None                 # ALWAYS counted when the provider can be reached, also as the fallback of a local embedder
    rep.update(model=model_id or rep["model"], route=(f"local embedder first, provider {getattr(provider, 'name', '?')} as fallback" if local and use_provider else
                                                      "local embedder (no provider request)" if local else f"provider {getattr(provider, 'name', '?')}"))
    budgets = budgets_of(provider) if use_provider else None
    rpd = lim.rpd if lim else None
    if budgets is not None and model_id and rpd:
        rep["counter_before"] = budgets.used_today(model_id)
    elif use_provider:
        rep["counter_note"] = "not available (no rpd configured)" if rpd is None else "n/a (no budget counter for this route)"
    dim_raw = (env.get("AI_EMBEDDING_DIM") or "").strip()
    expected_dim = int(dim_raw) if dim_raw.isdigit() else None
    per_input = opts.counting == "per-input" and use_provider
    used_eff = max(rep["counter_before"] or 0, opts.assume_used_today)
    rep["assumed_used_today"], rep["daily_ceiling"] = opts.assume_used_today, opts.daily_ceiling
    allowed_inputs = min(opts.max_requests, (rpd - used_eff) if rpd else opts.max_requests)
    if opts.daily_ceiling is not None:
        allowed_inputs = min(allowed_inputs, opts.daily_ceiling - used_eff)
    if opts.daily_ceiling is not None and allowed_inputs <= 0:
        return done(EXIT_QUOTA, f"STOP: {used_eff} requests are already used today (counter or --assume-used-today) and the daily ceiling is {opts.daily_ceiling}; nothing was sent")
    pacer = InputPacer(lim.rpm if lim else PACE_RPM, clock, sleep) if per_input else None
    if counting is not None:
        gw.ai.provider = counting
    code, reason = EXIT_OK, None
    queue: deque[tuple[list[str], bool]] = deque((b, False) for b in plan.batches)
    inputs_sent = extra = 0
    try:
        while queue:
            ids_b, split = queue.popleft()
            n = len(ids_b)
            if split:
                if extra >= BISECT_EXTRA:
                    code, reason = EXIT_FAIL, f"STOP: {BISECT_EXTRA} extra requests were used to isolate rejected rows and it is not finished; look at the rows listed below"
                    break
                extra += 1
                rep["bisect_calls"] += 1
            if counting is not None:
                if per_input and inputs_sent + n > allowed_inputs:
                    code, reason = EXIT_QUOTA, (f"STOP: per-input counting: {inputs_sent} inputs sent and the next {n} would exceed {allowed_inputs} "
                                                f"(min of --max-requests and the daily room); rerun to continue with what is still missing")
                    break
                if not per_input and counting.http_requests + math.ceil(n / _EMBED_BATCH) > opts.max_requests:
                    code, reason = EXIT_QUOTA, f"STOP: --max-requests {opts.max_requests} would be exceeded by the next batch; rerun to continue with what is still missing"
                    break
            if pacer is not None:
                pacer.wait(n)
            inputs_sent += n
            try:
                res = gw.embed_cases(ids_b, SYSTEM_ACTOR, only_missing=True, expected_dim=expected_dim, max_chars=MAX_CHARS)
            except Exception as e:                                          # noqa: BLE001  (classified; never retried, never looped)
                kind, why = classify(e)
                if kind == EXIT_FAIL and isolatable(e):
                    if n == 1:
                        rep["bad_rows"][ids_b[0]] = why.split(". The failed")[0]
                    else:
                        queue.appendleft((ids_b[n // 2:], True))
                        queue.appendleft((ids_b[:n // 2], True))
                    continue
                code, reason = kind, f"STOP: {why}"
                break
            rep["batches_done"] += 1
            rep["embedded"] += res["embedded"]
            rep["embedded_local" if res["source"] == "local_m7" else "embedded_provider"] += res["embedded"]
            rep["local_fallbacks"] += any(w.startswith("LOCAL_EMBEDDER_FAILED") for w in res["warnings"])
            rep["skipped_empty"] += len(res["skipped_empty"])
            rep["skipped_existing"] += len(res["skipped_existing"])
            rep["failed"] += len(res["failed"])
            if res["provider_called"]:
                rep["tokens"] += sum(plan.tokens.get(i, 0) for i in ids_b)
            if expected_dim is None and res["dim"]:
                expected_dim = res["dim"]                                   # the first valid batch fixes the dimension of the run
            if res["failed"]:
                code, reason = EXIT_FAIL, f"STOP: {len(res['failed'])} vector(s) of a batch could not be stored (database error); the rest of the run was not started"
                break
        if code == EXIT_OK and rep["bad_rows"] and rep["embedded"] == 0:
            code, reason = EXIT_FAIL, f"STOP: every row failed ({len(rep['bad_rows'])} rejected by the provider); nothing was stored"
    except KeyboardInterrupt:
        code, reason = EXIT_INTERRUPTED, "STOP: interrupted; what was stored is kept"
    finally:
        if counting is not None:
            gw.ai.provider = provider
            rep.update(embed_calls=counting.embed_calls, http_requests=counting.http_requests)
        if budgets is not None and model_id and rpd:
            rep["counter_after"] = budgets.used_today(model_id)
            rep["counter_delta"] = rep["counter_after"] - (rep["counter_before"] or 0)
    return done(code, reason)


def build_parser() -> argparse.ArgumentParser:
    class Parser(argparse.ArgumentParser):
        def error(self, message: str):                                      # argparse exits with 2, which this script reserves for "stopped for quota"
            self.print_usage(sys.stderr)
            self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")

    def bounded(lo: int, hi: int | None = None):
        def parse(s: str) -> int:
            n = int(s)
            if n < lo or (hi is not None and n > hi):
                raise argparse.ArgumentTypeError(f"must be {lo}..{hi}" if hi else f"must be >= {lo}")
            return n
        return parse

    ap = Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="no provider call, no write: print the plan, tokens, minutes and the requests under assumptions A and B")
    ap.add_argument("--limit", type=bounded(1), default=None, help="embed at most this many eligible cases (the oldest without an embedding; empty/over-long ones do not count)")
    ap.add_argument("--batch-size", type=bounded(1, MAX_BATCH), default=DEFAULT_BATCH, help=f"cases per provider.embed call (default {DEFAULT_BATCH}, max {MAX_BATCH})")
    ap.add_argument("--max-requests", type=bounded(1), default=DEFAULT_MAX_REQUESTS,
                    help=f"stop before exceeding this many HTTP requests (default {DEFAULT_MAX_REQUESTS}); with --counting per-input it counts inputs")
    ap.add_argument("--daily-ceiling", type=bounded(1), default=None, help="HARD STOP: never let today's embedding requests pass this number (the owner keeps a reserve for runtime use and calibration)")
    ap.add_argument("--assume-used-today", type=bounded(0), default=0, help="requests AI Studio already showed today, which the local counter never saw (the larger of this and the counter is used)")
    ap.add_argument("--counting", choices=COUNTING, default=None, help=f"required for a run of more than {PROBE_INPUTS} inputs: how AI Studio's usage page counted the probe (a batch call, or every input)")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    code, _ = execute(Options(dry_run=a.dry_run, limit=a.limit, batch_size=a.batch_size, max_requests=a.max_requests, counting=a.counting,
                        daily_ceiling=a.daily_ceiling, assume_used_today=a.assume_used_today))
    return code


if __name__ == "__main__":
    sys.exit(main())
