"""Deterministic similarity signals for case fusion (Section 37)."""
from __future__ import annotations

import math
from collections import Counter
from typing import Sequence

from ..local.featurizer import char_wb_ngrams, normalize_text

_EARTH_RADIUS_M = 6_371_008.8


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def lexical_similarity(a: str | None, b: str | None) -> float:
    """Char-trigram cosine. Language/script sensitive: cross-script pairs score ~0."""
    if not a or not b:
        return 0.0
    ca = Counter(char_wb_ngrams(normalize_text(a), (3, 3)))
    cb = Counter(char_wb_ngrams(normalize_text(b), (3, 3)))
    if not ca or not cb:
        return 0.0
    dot = sum(v * cb.get(k, 0) for k, v in ca.items())
    na = math.sqrt(sum(v * v for v in ca.values()))
    nb = math.sqrt(sum(v * v for v in cb.values()))
    return dot / (na * nb) if na and nb else 0.0


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity clipped to [0, 1]."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if not na or not nb:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


def geospatial_signal(distance_m: float, radius_m: float) -> float:
    return max(0.0, 1.0 - distance_m / radius_m)


def temporal_signal(age_hours: float, window_days: float) -> float:
    return max(0.0, 1.0 - age_hours / (24.0 * window_days))


def category_signal(cat_a: str, sub_a: str | None, cat_b: str, sub_b: str | None) -> float:
    if cat_a != cat_b:
        return 0.0
    return 1.0 if sub_a and sub_a == sub_b else 0.5
