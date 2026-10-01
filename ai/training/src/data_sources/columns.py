"""Header resolution, tolerant readers and parsing helpers for external tabular files."""
from __future__ import annotations

import csv
import gzip
import json
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator

from .errors import SchemaMismatch

_TS_FORMATS = ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M", "%m/%d/%Y", "%Y-%m-%d")


def norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(h).casefold()).strip("_")


class ColumnResolver:
    """Maps canonical field names to the actual header names present in a file.

    Aliases are matched after normalisation (case, spaces, punctuation), so the Socrata API form
    ``complaint_type`` and the CSV-export form ``Complaint Type`` both resolve. Required columns that
    cannot be resolved raise :class:`SchemaMismatch` listing the real headers -- we never guess.
    """

    def __init__(self, headers: Iterable[str], aliases: dict[str, list[str]], required: set[str]):
        by_norm = {norm_header(h): h for h in headers}
        self.headers = list(by_norm.values())
        self.map: dict[str, str | None] = {}
        for canon, names in aliases.items():
            self.map[canon] = next((by_norm[norm_header(n)] for n in names if norm_header(n) in by_norm), None)
        missing = sorted(c for c in required if self.map.get(c) is None)
        if missing:
            raise SchemaMismatch(f"missing required column(s) {missing}. Available headers: {sorted(self.headers)}. "
                                 f"Update the adapter aliases only after confirming the real column names.")

    def get(self, row: dict, canon: str):
        col = self.map.get(canon)
        if col is None:
            return None
        v = row.get(col)
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v


def _open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8-sig", newline="")
    return path.open("r", encoding="utf-8-sig", newline="")


def sniff_headers(path: Path, probe: int = 200) -> list[str]:
    path = Path(path)
    name = path.name.lower().removesuffix(".gz")
    if name.endswith(".csv"):
        with _open_text(path) as fh:
            return next(csv.reader(fh), [])
    keys: dict[str, None] = {}
    for i, row in enumerate(iter_rows(path)):
        keys.update(dict.fromkeys(row))
        if i >= probe:
            break
    return list(keys)


def iter_rows(path: Path) -> Iterator[dict]:
    """Stream rows from .csv / .jsonl / .json (array) (optionally .gz)."""
    path = Path(path)
    name = path.name.lower().removesuffix(".gz")
    if name.endswith(".csv"):
        with _open_text(path) as fh:
            yield from csv.DictReader(fh)
    elif name.endswith(".jsonl") or name.endswith(".ndjson"):
        with _open_text(path) as fh:
            for line in fh:
                if line.strip():
                    yield json.loads(line)
    elif name.endswith(".json"):
        with _open_text(path) as fh:
            data = json.load(fh)
        yield from data if isinstance(data, list) else data.get("data", [])
    else:
        raise SchemaMismatch(f"unsupported file type: {path.name} (use .csv, .jsonl or .json)")


def parse_ts(value) -> str | None:
    """Return an ISO-8601 *naive* timestamp (source-local; the portals do not state a timezone)."""
    if value in (None, ""):
        return None
    s = str(value).strip()
    for fmt in _TS_FORMATS:
        try:
            return datetime.strptime(s, fmt).isoformat()
        except ValueError:
            continue
    return None


def parse_coord(value, lo: float, hi: float) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if lo <= v <= hi and v == v else None


def parse_bool(value) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    s = str(value).strip().casefold()
    if s in {"true", "t", "1", "yes", "y"}:
        return True
    if s in {"false", "f", "0", "no", "n", ""}:
        return False
    return None


def reservoir(items: Iterable, k: int | None, seed: int = 0) -> Iterator:
    """Deterministic streaming sample of at most ``k`` items (all items if ``k`` is None)."""
    if k is None:
        yield from items
        return
    rng = random.Random(seed)
    pool: list = []
    for n, it in enumerate(items):
        if len(pool) < k:
            pool.append(it)
        else:
            j = rng.randint(0, n)
            if j < k:
                pool[j] = it
    yield from pool
