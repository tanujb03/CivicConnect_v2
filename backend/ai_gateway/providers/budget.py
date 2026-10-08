"""Per-model request budgets for the free AI tiers (requests per minute, requests per day, tokens per minute).

The limits come from ``model_limits.json`` (quota numbers read from the providers' pages on 2026-10-08, NOT model choices) overridden by ``AI_MODEL_LIMITS``::

    AI_MODEL_LIMITS="some-model=5/20/250000,other-model=15/500/-"     # rpm/rpd/tpm, "-" or empty = no limit;  AI_MODEL_LIMITS=off  disables every budget

Behaviour before each request (``ModelBudgets.acquire``):

* **per-minute budget full** (rpm, or tpm for the request's estimated tokens): wait for a slot, but only up to ``AI_BUDGET_MAX_WAIT_S`` (default 8 s); a longer wait is refused at once;
* **daily budget spent**: the request is NOT sent; ``BudgetSpent`` (a ``ProviderUnavailable``) is raised so the caller degrades to its fallback route. The day is the provider's quota day
  (``AI_QUOTA_TZ``, default America/Los_Angeles: Google resets at midnight Pacific; UTC when the time zone database is missing). The daily counter lives in Redis (shared by every
  process of the machine) with an in-process fallback when Redis is down; it is logged ONCE when a budget is spent, never per request.

Minute windows are per process. The counters know only OUR requests: another client using the same key (AI Studio's playground, a second laptop) spends the same quota, which the
provider's own 429 and the cooldown in ``openai_compat`` then catch.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

from ai.inference.errors import ProviderUnavailable
from backend.core.rate_limit import _Backend

log = logging.getLogger("civicconnect.ai.budget")

LIMITS_FILE = Path(__file__).with_name("model_limits.json")
DAY_KEY_TTL_S = 26 * 3600
WINDOW_S = 60.0


class BudgetSpent(ProviderUnavailable):
    """The model's budget is used up (daily) or too full to wait for (minute): no request was sent."""


@dataclass(frozen=True)
class Limits:
    rpm: int | None = None
    rpd: int | None = None
    tpm: int | None = None
    per_input: bool = False        # the provider counts every INPUT of a batch call as one request (measured for the embedding model, 2026-10-08: a batch of 10 cost 10)


def _num(value: object) -> int | None:
    if value in (None, "", "-"):
        return None
    n = int(str(value).strip())
    return n if n > 0 else None


def load_default_limits(path: Path = LIMITS_FILE) -> dict[str, Limits]:
    rows = json.loads(path.read_text(encoding="utf-8")).get("models", {})
    return {m: Limits(_num(v.get("rpm")), _num(v.get("rpd")), _num(v.get("tpm")), v.get("count") == "per_input") for m, v in rows.items()}


def parse_limits(spec: str | None, base: Mapping[str, Limits] | None = None) -> dict[str, Limits]:
    """``base`` plus the ``AI_MODEL_LIMITS`` overrides (``model=rpm/rpd/tpm[/input]``; a fourth field ``input`` = every input of a batch counts as one request). ``off`` returns an empty
    table (budgets disabled)."""
    out = dict(load_default_limits() if base is None else base)
    spec = (spec or "").strip()
    if spec.lower() == "off":
        return {}
    for item in filter(None, (s.strip() for s in spec.split(","))):
        model, _, rest = item.partition("=")
        parts = (rest.split("/") + ["", "", "", ""])[:4]
        if not model.strip() or not rest:
            raise ValueError(f"AI_MODEL_LIMITS entry {item!r} must look like model=rpm/rpd/tpm")
        try:
            out[model.strip()] = Limits(_num(parts[0]), _num(parts[1]), _num(parts[2]), parts[3].strip().lower() in ("input", "per_input"))
        except ValueError as exc:
            raise ValueError(f"AI_MODEL_LIMITS entry {item!r}: rpm/rpd/tpm must be whole numbers or '-'") from exc
    return out


def quota_day(now: float, tz_name: str) -> str:
    """The provider's quota day (``YYYY-MM-DD``) at epoch ``now``."""
    when = datetime.fromtimestamp(now, timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        when = when.astimezone(ZoneInfo(tz_name))
    except Exception:
        pass                                                    # no tz database: UTC days
    return when.strftime("%Y-%m-%d")


class ModelBudgets:
    def __init__(self, limits: Mapping[str, Limits], *, provider: str, clock: Callable[[], float] = time.time, sleep: Callable[[float], None] = time.sleep,
                 max_wait_s: float = 8.0, tz_name: str = "America/Los_Angeles", redis_getter: Callable[[], object | None] | None = None) -> None:
        self.limits, self.provider, self._clock, self._sleep = dict(limits), provider, clock, sleep
        self.max_wait_s, self.tz_name = max_wait_s, tz_name
        self._redis_getter = redis_getter
        self._lock = threading.RLock()
        self._windows: dict[str, deque[tuple[float, int, int]]] = {}    # model -> (time, tokens, requests)
        self._days: dict[str, int] = {}                          # in-process fallback: "model|day" -> count
        self._reported: set[str] = set()                         # "model|day" whose spent-budget log line was written
        self._b = _Backend()                                     # Redis-or-memory plumbing with back-off and a once-a-minute warning

    @classmethod
    def from_env(cls, env: Mapping[str, str], *, provider: str, **kw) -> "ModelBudgets | None":
        limits = parse_limits(env.get("AI_MODEL_LIMITS"))
        if not limits:
            return None
        return cls(limits, provider=provider, max_wait_s=float(env.get("AI_BUDGET_MAX_WAIT_S", "8")), tz_name=env.get("AI_QUOTA_TZ", "America/Los_Angeles"), **kw)

    # ------------------------------------------------------------------------------------------ daily counter (Redis, in-process fallback)
    def _day_key(self, model: str) -> str:
        return f"civic:aibudget:rpd:{self.provider}:{model}:{quota_day(self._clock(), self.tz_name)}"

    def _redis(self):
        if self._redis_getter is not None:
            return self._redis_getter()
        return self._b.client()

    def used_today(self, model: str) -> int:
        key = self._day_key(model)
        r = self._redis()
        if r is not None:
            try:
                return int(r.get(key) or 0)
            except Exception as exc:
                self._b.failed(exc)
        with self._lock:
            return self._days.get(key, 0)

    def _count_today(self, model: str, units: int = 1) -> int:
        """Counts ``units`` requests and returns the new total."""
        key = self._day_key(model)
        r = self._redis()
        if r is not None:
            try:
                pipe = r.pipeline()
                pipe.incrby(key, units)
                pipe.expire(key, DAY_KEY_TTL_S)
                return int(pipe.execute()[0])
            except Exception as exc:
                self._b.failed(exc)
        with self._lock:
            self._days[key] = self._days.get(key, 0) + units
            return self._days[key]

    def _spent(self, model: str, lim: Limits, used: int) -> BudgetSpent:
        key = f"{model}|{quota_day(self._clock(), self.tz_name)}"
        with self._lock:
            first = key not in self._reported
            self._reported.add(key)
        if first:
            log.warning("AI budget spent: %s model=%s used %d of %d requests today (quota day %s, %s); requests degrade to the fallback until the reset",
                        self.provider, model, used, lim.rpd, quota_day(self._clock(), self.tz_name), self.tz_name)
        return BudgetSpent(f"{self.provider}: daily budget of {model} is spent ({used}/{lim.rpd} requests today); request not sent", status_code=429)

    # ------------------------------------------------------------------------------------------ the gate
    def acquire(self, model: str, tokens: int = 0, units: int = 1) -> None:
        """Wait for / refuse one provider call. ``units`` = the number of inputs of the call; it only matters for models whose limits say ``per_input`` (every input counts as one
        request in the minute window and in the daily counter); for other models a call is one request whatever its size."""
        lim = self.limits.get(model)
        if lim is None or not (lim.rpm or lim.rpd or lim.tpm):
            return
        n = max(1, int(units)) if lim.per_input else 1
        if lim.rpd and (used := self.used_today(model)) + n > lim.rpd:
            raise self._spent(model, lim, used)
        if lim.tpm and tokens > lim.tpm:
            raise BudgetSpent(f"{self.provider}: one request of about {tokens} tokens exceeds the {lim.tpm} tokens-per-minute budget of {model}; request not sent", status_code=429)
        if lim.rpm and n > lim.rpm:
            raise BudgetSpent(f"{self.provider}: one call of {n} inputs exceeds the {lim.rpm} requests-per-minute budget of {model} (every input counts); request not sent", status_code=429)
        waited = 0.0
        while True:
            with self._lock:
                now = self._clock()
                win = self._windows.setdefault(model, deque())
                while win and win[0][0] <= now - WINDOW_S:
                    win.popleft()
                wait = 0.0
                if lim.rpm and sum(u for _, _, u in win) + n > lim.rpm:
                    need, freed = sum(u for _, _, u in win) + n - lim.rpm, 0
                    for ts, _, u in win:
                        freed += u
                        wait = max(wait, ts + WINDOW_S - now)
                        if freed >= need:
                            break
                if lim.tpm and sum(t for _, t, _ in win) + tokens > lim.tpm:
                    need, freed = sum(t for _, t, _ in win) + tokens - lim.tpm, 0
                    for ts, t, _ in win:
                        freed += t
                        wait = max(wait, ts + WINDOW_S - now)
                        if freed >= need:
                            break
                if wait <= 0:
                    win.append((now, tokens, n))
                    break
            if waited + wait > self.max_wait_s:
                raise BudgetSpent(f"{self.provider}: per-minute budget of {model} is full (would wait {wait:.0f} s, limit {self.max_wait_s:.0f} s); request not sent", status_code=429)
            self._sleep(wait + 0.05)
            waited += wait + 0.05
        if lim.rpd and (used := self._count_today(model, n)) > lim.rpd:       # another process spent the last requests meanwhile
            raise self._spent(model, lim, used - n)

    def snapshot(self) -> dict[str, dict]:
        """For diagnostics: per limited model, the day's usage and the limits (no secrets)."""
        return {m: {"rpm": lim.rpm, "rpd": lim.rpd, "tpm": lim.tpm, "used_today": self.used_today(m) if lim.rpd else None} for m, lim in self.limits.items()}
