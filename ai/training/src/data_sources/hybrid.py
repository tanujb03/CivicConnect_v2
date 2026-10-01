"""Hybrid (real + synthetic) training-set assembly with leakage guards.

Real records are only eligible for supervised *text* training when they are genuine citizen narratives
with an exact mapped label and are not in a holdout. Synthetic records augment (multilingual coverage,
code-mixing, rare taxonomy cases) and never replace real data; provenance is preserved on every row.
"""
from __future__ import annotations

import random
from collections import Counter

from .canonical import CaseRecord


class HybridDataError(Exception):
    pass


def eligible_real_text(r: CaseRecord) -> str | None:
    """Return None if eligible, else the exclusion reason."""
    if r.provenance.kind != "real_public":
        return "not_real"
    if r.text_origin != "citizen_narrative" or not r.text:
        return "no_citizen_narrative_text"
    if r.mapping_status != "exact":
        return "no_exact_mapped_label"
    if r.split_hint in ("holdout", "test"):
        return "holdout"
    return None


def build_hybrid_training_set(real: list[CaseRecord], synthetic: list[CaseRecord], *, max_synthetic_per_real: float | None = None,
                              seed: int = 0) -> tuple[list[CaseRecord], dict]:
    reasons: Counter = Counter()
    real_ok = []
    for r in real:
        why = eligible_real_text(r)
        if why:
            reasons[why] += 1
        else:
            real_ok.append(r)
    bad = [s for s in synthetic if s.provenance.kind != "synthetic"]
    if bad:
        raise HybridDataError("synthetic list contains non-synthetic records")
    if not real_ok:
        raise HybridDataError(f"no eligible real records (exclusions: {dict(reasons)}). A text classifier cannot be trained on real data "
                              f"that has no citizen narrative text; use the synthetic-only track or acquire narrative data.")
    synth = sorted(synthetic, key=lambda r: r.record_id)
    random.Random(seed).shuffle(synth)
    if max_synthetic_per_real is not None:
        synth = synth[: int(len(real_ok) * max_synthetic_per_real)]
    mixed = real_ok + synth
    ids = [r.record_id for r in mixed]
    if len(ids) != len(set(ids)):
        raise HybridDataError("duplicate record ids in the mixed set")
    held = {r.record_id for r in real if r.split_hint in ("holdout", "test")}
    if held & set(ids):
        raise HybridDataError("a holdout record leaked into the training set")
    report = {"n_real": len(real_ok), "n_synthetic": len(synth), "real_share": round(len(real_ok) / len(mixed), 4),
              "real_excluded": dict(reasons), "synthetic_per_real": round(len(synth) / len(real_ok), 3)}
    return mixed, report
