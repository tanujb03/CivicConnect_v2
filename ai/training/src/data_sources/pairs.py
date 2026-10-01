"""Build REAL duplicate-evaluation pairs from agency-assigned duplicate/parent links.

Positives: (child, parent) where the source flags the child as a duplicate and the parent is present.
Negatives: nearby, in-window, same-mapped-category requests that are not linked to each other. Negatives
may include real duplicates the agency never linked (label noise) -> precision is a conservative bound.
Pairs carry the source's provenance; no narrative text is included (none exists), so the semantic
signal is intentionally not evaluated on real pairs.
"""
from __future__ import annotations

import random
from collections import defaultdict
from datetime import datetime

from ai.inference.fusion.similarity import haversine_m

from .canonical import CaseRecord, PairRecord, PairSide
from .splits import grid_cell


def _side(r: CaseRecord) -> PairSide:
    return PairSide(case_id=r.record_id, category=r.category or "", subcategory=r.subcategory, latitude=r.latitude,
                    longitude=r.longitude, created_at=r.created_at, text=None, language=None)


def _usable(r: CaseRecord) -> bool:
    return bool(r.category and r.latitude is not None and r.longitude is not None and r.created_at)


def build_pairs_from_parent_links(records: list[CaseRecord], *, neg_per_pos: int = 1, radius_m: float = 150.0,
                                  window_days: float = 30.0, seed: int = 0) -> tuple[list[PairRecord], dict]:
    rng = random.Random(seed)
    by_id = {r.record_id: r for r in records}
    linked: set[frozenset] = set()
    for r in records:
        if r.parent_record_id:
            linked.add(frozenset((r.record_id, r.parent_record_id)))
    cell = radius_m / 111_000.0
    index: dict[tuple, list[CaseRecord]] = defaultdict(list)
    for r in records:
        if _usable(r):
            index[(r.category, grid_cell(r.latitude, r.longitude, cell))].append(r)

    pairs: list[PairRecord] = []
    stats = {"duplicate_flagged": 0, "parent_missing": 0, "positives": 0, "negatives": 0, "no_negative_found": 0,
             "positives_category_differs": 0}
    for child in sorted(records, key=lambda r: r.record_id):
        if not child.duplicate_flag:
            continue
        stats["duplicate_flagged"] += 1
        parent = by_id.get(child.parent_record_id or "")
        if parent is None:
            stats["parent_missing"] += 1
            continue
        if not (_usable(child) and _usable(parent)):
            continue
        if child.category != parent.category:
            stats["positives_category_differs"] += 1
        pid = f"{child.provenance.source_id}-dup-{child.provenance.source_record_id}"
        pairs.append(PairRecord(pair_id=pid, provenance=child.provenance.model_copy(update={"label_origin": "source_category"}),
                                label=1, pair_type="agency_linked_duplicate", a=_side(child), b=_side(parent), split_hint=child.split_hint))
        stats["positives"] += 1
        # negatives: same category, nearby cell neighbourhood, within window, never linked
        cx, cy = (int(x) for x in grid_cell(child.latitude, child.longitude, cell).split(":"))
        cands = []
        for dx in (-2, -1, 0, 1, 2):
            for dy in (-1, 0, 1):
                cands.extend(index.get((child.category, f"{cx + dx}:{cy + dy}"), []))
        t_child = datetime.fromisoformat(child.created_at)
        ok = [c for c in cands if c.record_id != child.record_id and c.record_id != parent.record_id and not c.duplicate_flag
              and frozenset((child.record_id, c.record_id)) not in linked
              and haversine_m(child.latitude, child.longitude, c.latitude, c.longitude) <= radius_m
              and abs((datetime.fromisoformat(c.created_at) - t_child).total_seconds()) <= window_days * 86400]
        ok.sort(key=lambda c: c.record_id)
        rng.shuffle(ok)
        if not ok:
            stats["no_negative_found"] += 1
        for neg in ok[:neg_per_pos]:
            pairs.append(PairRecord(pair_id=f"{pid}-neg-{neg.provenance.source_record_id}",
                                    provenance=child.provenance.model_copy(update={"label_origin": "source_category"}),
                                    label=0, pair_type="unlinked_nearby_same_type", a=_side(child), b=_side(neg), split_hint=child.split_hint))
            stats["negatives"] += 1
    return pairs, stats
