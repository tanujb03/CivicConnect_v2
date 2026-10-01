"""Leakage-aware holdout assignment for real data (time / group / spatial-cell / country)."""
from __future__ import annotations

import hashlib
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")


def _with_split(rec, split: str):
    return rec.model_copy(update={"split_hint": split})


def time_holdout(records: Iterable[T], holdout_after: str) -> list[T]:
    """Most-recent requests become the holdout (simulates deploying on future data). Records without a
    timestamp are excluded from both sides (``split_hint`` stays None)."""
    out = []
    for r in records:
        c = getattr(r, "created_at", None)
        out.append(r if not c else _with_split(r, "holdout" if c[:10] >= holdout_after else "train"))
    return out


def group_holdout(records: Iterable[T], group_fn: Callable[[T], str | None], holdout_groups: set[str]) -> list[T]:
    """Hold out whole groups (city district, country, road-survey source...) so near-identical rows cannot leak."""
    out = []
    for r in records:
        g = group_fn(r)
        out.append(r if g is None else _with_split(r, "holdout" if g in holdout_groups else "train"))
    return out


def grid_cell(lat: float, lon: float, cell_deg: float = 0.01) -> str:
    return f"{round(lat / cell_deg)}:{round(lon / cell_deg)}"


def spatial_cell_group(rec, cell_deg: float = 0.01) -> str | None:
    if getattr(rec, "latitude", None) is None or getattr(rec, "longitude", None) is None:
        return None
    return grid_cell(rec.latitude, rec.longitude, cell_deg)


def hash_fraction(key: str, seed: int = 0) -> float:
    return int(hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()[:12], 16) / 16 ** 12


def spatial_holdout(records: Iterable[T], holdout_fraction: float = 0.2, seed: int = 0, cell_deg: float = 0.01) -> list[T]:
    """Deterministic spatial-cell holdout: whole ~1 km cells go to the holdout."""
    out = []
    for r in records:
        g = spatial_cell_group(r, cell_deg)
        out.append(r if g is None else _with_split(r, "holdout" if hash_fraction(g, seed) < holdout_fraction else "train"))
    return out
