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


RESOLVED_STATES = {"VERIFIED", "RESOLVED", "REJECTED"}


def subcategory_growth(cases: Sequence[Case], now: datetime, *, recent_days: int = 14, baseline_days: int = 90, min_recent: int = 8,
                       min_relative_ratio: float = 2.0) -> dict:
    """Unusual category growth (§11 AI-5): a subcategory's recent daily rate vs its own baseline rate, DIVIDED by the whole city's same ratio so that
    city-wide growth is not reported as category growth. Needs >= ``min_recent`` recent cases (baseline floor of 1 case per window)."""
    from collections import Counter
    recent_lo, base_lo = now - timedelta(days=recent_days), now - timedelta(days=recent_days + baseline_days)
    rec, base = Counter(), Counter()
    for c in cases:
        sub = c.get("subcategory")
        if not sub or sub == "unclassified":
            continue
        t = _ts(c)
        if t >= recent_lo:
            rec[sub] += 1
        elif t >= base_lo:
            base[sub] += 1
    n_rec, n_base = sum(rec.values()), sum(base.values())
    city_ratio = (n_rec / recent_days) / (max(n_base, 1) / baseline_days)
    items = []
    for sub, n in rec.items():
        if n < min_recent:
            continue
        ratio = (n / recent_days) / (max(base[sub], 1) / baseline_days)
        rel = ratio / city_ratio if city_ratio else 0.0
        if rel >= min_relative_ratio:
            items.append({"subcategory": sub, "recent_cases": n, "baseline_cases": base[sub], "relative_growth": round(rel, 2)})
    return {"city_growth_ratio": round(city_ratio, 2), "items": sorted(items, key=lambda i: -i["relative_growth"])}


def sla_risk(cases: Sequence[Case], now: datetime, *, horizon_hours: int = 24) -> dict:
    """SLA-risk pattern (§11 AI-5): open cases already past their SLA deadline or due within ``horizon_hours``, overall and per department."""
    from collections import Counter
    horizon = now + timedelta(hours=horizon_hours)
    open_, breached, due = [], [], []
    for c in cases:
        if c.get("status") in RESOLVED_STATES or not c.get("sla_deadline"):
            continue
        dl = datetime.fromisoformat(str(c["sla_deadline"]).replace("Z", "+00:00"))
        open_.append(c)
        if dl < now:
            breached.append(c)
        elif dl <= horizon:
            due.append(c)
    by_dep = Counter(c.get("department_id") or "unassigned" for c in breached)
    return {"open": len(open_), "breached": len(breached), "due_within_horizon": len(due), "horizon_hours": horizon_hours,
            "breached_by_department": [{"department_id": d, "breached": n} for d, n in sorted(by_dep.items(), key=lambda kv: (-kv[1], kv[0]))]}


def geographic_concentration(cases: Sequence[Case], now: datetime, *, recent_days: int = 14, top_k: int = 3) -> dict:
    """Geographic concentration (§11 AI-5): the share of recent cases that fall in the ``top_k`` wards."""
    from collections import Counter
    lo = now - timedelta(days=recent_days)
    wards = Counter(c["ward_id"] for c in cases if c.get("ward_id") and _ts(c) >= lo)
    total = sum(wards.values())
    top = wards.most_common(top_k)
    return {"recent_cases": total, "recent_days": recent_days, "top_k": top_k,
            "top_wards": [{"ward_id": w, "cases": n, "share_pct": round(100 * n / total) if total else 0} for w, n in top],
            "top_k_share_pct": round(100 * sum(n for _, n in top) / total) if total else 0}
