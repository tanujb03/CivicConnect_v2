"""Leakage audits for prepared records (run before ANY evaluation claim; also run by ``cli leakage-audit``).

Checks (each returns plain data; ``audit_task`` decides which apply from the task's ``leakage_checks`` and
reports ``blocking`` problems):

* target_determinism   - is the target a (near-)deterministic function of the allowed inputs? Then predicting it is vacuous.
* split_straddle       - do near-identical items (same group) sit on both sides of the train/holdout split?
* spatiotemporal       - same category, same ~200 m cell, same ISO week on both sides of the split (complaint bursts)
* text_contains_label  - does the free text echo the label it is supposed to predict?
* censoring_report     - how many outcomes are right-censored (unresolved) and therefore not a complete sample?
* views_clean          - the task view exposes only allowed roles (structural check on real records)
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Callable, Iterable, Sequence

from .canonical import CaseRecord
from .column_roles import TaskPolicy
from .splits import grid_cell

VACUOUS_PURITY = 0.99
TEXT_ECHO_LIMIT = 0.05
_HOLD = ("holdout", "test", "val")


def target_determinism(records: Sequence[CaseRecord], policy: TaskPolicy, task: str, target_role: str, key_roles: Sequence[str] | None = None) -> dict:
    inputs, _ = policy.allowed_roles(task)
    keys = list(key_roles) if key_roles is not None else inputs
    groups: dict[tuple, Counter] = defaultdict(Counter)
    overall: Counter = Counter()
    for r in records:
        v = policy.view(r, task)
        t = v.targets.get(target_role) if target_role in v.targets else policy.read(r, task, target_role)
        if t is None:
            continue
        key = tuple(v.inputs.get(k) for k in keys)
        groups[key][t] += 1
        overall[t] += 1
    n = sum(overall.values())
    if not n:
        return {"n": 0, "purity": None, "vacuous": None, "note": "no rows with a target value"}
    purity = sum(c.most_common(1)[0][1] for c in groups.values()) / n
    baseline = overall.most_common(1)[0][1] / n
    return {"n": n, "key_roles": keys, "n_groups": len(groups), "purity": round(purity, 4), "majority_baseline": round(baseline, 4),
            "lift_over_baseline": round(purity - baseline, 4), "vacuous": purity >= VACUOUS_PURITY,
            "note": "purity = accuracy of predicting the majority target within each input group (an upper bound on what these inputs can explain)"}


def split_straddle(records: Iterable, key_fn: Callable) -> dict:
    sides: dict[str, set[str]] = defaultdict(set)
    for r in records:
        sh = getattr(r, "split_hint", None)
        k = key_fn(r)
        if sh is None or k is None:
            continue
        sides[k].add("train" if sh == "train" else "holdout" if sh in _HOLD else sh)
    straddling = [k for k, s in sides.items() if {"train", "holdout"} <= s]
    return {"n_groups": len(sides), "straddling_groups": len(straddling), "straddle_share": round(len(straddling) / max(len(sides), 1), 4),
            "examples": sorted(map(str, straddling))[:5]}


def _week(created_at: str | None) -> str | None:
    if not created_at:
        return None
    y, w, _ = datetime.fromisoformat(created_at).isocalendar()
    return f"{y}-W{w:02d}"


def spatiotemporal_straddle(records: Sequence[CaseRecord], cell_deg: float = 0.002) -> dict:
    """Share of holdout rows whose (category, ~200 m cell, ISO week) also occurs in the training side."""
    train, hold = set(), []
    for r in records:
        if r.latitude is None or r.created_at is None or not r.category:
            continue
        key = (r.category, grid_cell(r.latitude, r.longitude, cell_deg), _week(r.created_at))
        if r.split_hint == "train":
            train.add(key)
        elif r.split_hint in _HOLD:
            hold.append(key)
    leaked = sum(k in train for k in hold)
    return {"holdout_rows": len(hold), "holdout_rows_with_train_twin": leaked, "share": round(leaked / max(len(hold), 1), 4),
            "note": "twins are not duplicates by definition, but a high share means train/holdout are not independent (bursts, repeated sites)"}


def text_contains_label(records: Sequence[CaseRecord], label_terms: Callable[[CaseRecord], Iterable[str]] | None = None) -> dict:
    n = hits = 0
    for r in records:
        if not r.text:
            continue
        n += 1
        terms = list(label_terms(r)) if label_terms else [t for t in (r.source_category, r.source_subcategory) if t]
        low = r.text.casefold()
        if any(t.casefold() in low for t in terms if len(t) >= 4):
            hits += 1
    rate = hits / n if n else None
    return {"n_text_rows": n, "echo_rate": None if rate is None else round(rate, 4), "blocking": bool(rate is not None and rate > TEXT_ECHO_LIMIT)}


def censoring_report(records: Sequence[CaseRecord]) -> dict:
    n = len(records)
    resolved = sum(1 for r in records if r.attributes.get("resolution_hours") is not None)
    return {"n": n, "with_resolution_time": resolved, "censored_or_unknown": n - resolved, "censored_share": round((n - resolved) / max(n, 1), 4),
            "note": "durations of resolved complaints only describe resolved complaints: unresolved ones are censored, not missing at random"}


def views_clean(records: Sequence[CaseRecord], policy: TaskPolicy, sample: int = 500) -> dict:
    bad: list[str] = []
    for task, t in policy.tasks.items():
        if t.status == "not_pursued":
            continue
        allowed = set(t.inputs) | set(t.targets)
        forb = policy.effective_forbidden(task)
        for r in records[:sample]:
            v = policy.view(r, task)
            leaked = (set(v.inputs) | set(v.targets)) - allowed
            leaked |= set(v.inputs) & forb
            if leaked:
                bad.append(f"{task}: {sorted(leaked)}")
                break
    return {"tasks_checked": len(policy.tasks), "violations": bad}


def audit_task(records: Sequence[CaseRecord], policy: TaskPolicy, task: str) -> dict:
    """Run the checks the task declares; ``passed`` is False if any blocking problem is found."""
    t = policy.tasks[task]
    out: dict = {"task": task, "checks": {}, "blocking": []}
    for chk in t.leakage_checks:
        if chk == "target_determinism":
            for tgt in t.targets:
                d = target_determinism(records, policy, task, tgt)
                out["checks"][f"target_determinism[{tgt}]"] = d
                if d.get("vacuous"):
                    out["blocking"].append(f"target {tgt!r} is (near-)deterministic given the inputs (purity {d['purity']}): evaluation would be vacuous")
        elif chk == "split_straddle":
            out["checks"]["spatiotemporal"] = d = spatiotemporal_straddle(records)
            if d["share"] > 0.5:
                out["blocking"].append(f"{d['share']:.0%} of holdout rows have a same-category/site/week twin in training")
        elif chk == "text_contains_label_rate":
            out["checks"][chk] = d = text_contains_label(records)
            if d["blocking"]:
                out["blocking"].append(f"free text echoes the label in {d['echo_rate']:.0%} of rows")
        elif chk == "censoring_reported":
            out["checks"][chk] = censoring_report(records)
    out["passed"] = not out["blocking"]
    return out
