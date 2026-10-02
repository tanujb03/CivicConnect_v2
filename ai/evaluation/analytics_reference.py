"""Deterministic REFERENCE implementations of the design's recurrence (§38) and hotspot (§39) detection.

The production numbers come from the backend's SQL (§40: "deterministic aggregation produces the facts, the LLM explains them").
These pure-Python versions exist so that (a) the synthetic demo city's planted ground truth can be recovered and scored, and (b) the
backend has an executable specification to compare its SQL against. AI never decides hotspots or recurrence.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Iterable, Mapping, Sequence

Case = Mapping


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000.0 * math.asin(math.sqrt(h))


def _ts(c: Case) -> datetime:
    return datetime.fromisoformat(str(c["created_at"]).replace("Z", "+00:00"))


def _pt(c: Case) -> tuple[float, float]:
    loc = c["location"]
    return float(loc["latitude"]), float(loc["longitude"])


def _components(pts: list[tuple[float, float]], radius_m: float) -> list[list[int]]:
    """Single-linkage connected components of points closer than ``radius_m`` (union-find)."""
    parent = list(range(len(pts)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            if abs(pts[i][0] - pts[j][0]) < 0.003 and haversine_m(pts[i], pts[j]) <= radius_m:
                parent[find(i)] = find(j)
    comps: dict[int, list[int]] = defaultdict(list)
    for i in range(len(pts)):
        comps[find(i)].append(i)
    return list(comps.values())


def recurring_sites(cases: Iterable[Case], *, radius_m: float = 150.0, window_days: float = 240.0, min_cases: int = 4) -> list[dict]:
    """Same subcategory, linked when within ``radius_m`` (single linkage), >= ``min_cases`` cases inside any ``window_days`` window.
    Returns sites with their case ids, how many were resolved/reopened (the §38 example: "2 previously resolved, 1 reopened")."""
    by_sub: dict[str, list[Case]] = defaultdict(list)
    for c in cases:
        if c.get("subcategory") and c["subcategory"] != "unclassified" and c.get("location"):
            by_sub[c["subcategory"]].append(c)
    sites = []
    for sub, items in by_sub.items():
        for idxs in _components([_pt(c) for c in items], radius_m):
            comp = sorted((items[i] for i in idxs), key=_ts)
            j = 0
            best: list[Case] = []
            for i in range(len(comp)):
                while (_ts(comp[i]) - _ts(comp[j])) > timedelta(days=window_days):
                    j += 1
                if i - j + 1 > len(best):
                    best = comp[j: i + 1]
            if len(best) >= min_cases:
                sites.append({"subcategory": sub, "case_ids": [c["id"] for c in best], "n_cases": len(best),
                              "n_resolved": sum(c.get("status") == "RESOLVED" for c in best), "n_reopened": sum(int(c.get("reopen_count", 0)) > 0 for c in best),
                              "center": {"latitude": round(sum(p[0] for p in map(_pt, best)) / len(best), 6), "longitude": round(sum(p[1] for p in map(_pt, best)) / len(best), 6)},
                              "first_at": best[0]["created_at"], "last_at": best[-1]["created_at"]})
    return sorted(sites, key=lambda s: -s["n_cases"])


def hotspots(cases: Sequence[Case], now: datetime, *, recent_days: int = 14, baseline_days: int = 90, cell_m: float = 350.0, min_recent: int = 8, min_ratio: float = 3.0) -> list[dict]:
    """Grid aggregation per (subcategory, cell): recent count vs the cell's rolling baseline rate (§39: "start with deterministic geospatial aggregation").
    A hotspot needs >= ``min_recent`` recent cases AND a recent daily rate >= ``min_ratio`` x the baseline daily rate (baseline floor of 1 case per window)."""
    lat_step = cell_m / 111_320.0
    recent_lo, base_lo = now - timedelta(days=recent_days), now - timedelta(days=recent_days + baseline_days)
    cells: dict[tuple, dict] = defaultdict(lambda: {"recent": [], "base": 0})
    for c in cases:
        if not c.get("location") or c.get("subcategory") in (None, "unclassified"):
            continue
        la, lo = _pt(c)
        lon_step = lat_step / max(math.cos(math.radians(la)), 0.1)
        key = (c["subcategory"], round(la / lat_step), round(lo / lon_step))
        t = _ts(c)
        if t >= recent_lo:
            cells[key]["recent"].append(c)
        elif t >= base_lo:
            cells[key]["base"] += 1
    out = []
    for (sub, ri, ci), v in cells.items():
        n = len(v["recent"])
        if n < min_recent:
            continue
        base_rate = max(v["base"], 1) / baseline_days
        if n / recent_days >= min_ratio * base_rate:
            las = [_pt(c)[0] for c in v["recent"]]
            los = [_pt(c)[1] for c in v["recent"]]
            out.append({"subcategory": sub, "cell": [ri, ci], "recent_cases": n, "baseline_cases": v["base"], "ratio_vs_baseline": round((n / recent_days) / base_rate, 2),
                        "center": {"latitude": round(sum(las) / n, 6), "longitude": round(sum(los) / n, 6)}, "case_ids": [c["id"] for c in v["recent"]]})
    return sorted(out, key=lambda h: -h["recent_cases"])
