"""Profile an externally downloaded tabular file BEFORE trusting any mapping.

Answers the questions the mapping tables and source cards leave open: which columns exist, what the
real category/descriptor values are, how much of the file the draft mapping covers, whether coordinates
and timestamps are usable, and -- importantly -- whether ANY column looks like free-text narrative.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from .columns import ColumnResolver, iter_rows, parse_coord, parse_ts, sniff_headers
from .mapping import CoverageReport, MappingTable


def profile_tabular(path: Path, aliases: dict[str, list[str]], match_fields: list[str], mapping: MappingTable | None,
                    *, max_rows: int = 200_000, top: int = 40) -> dict:
    headers = sniff_headers(path)
    cols = ColumnResolver(headers, aliases, set())          # never raises: we want to report what is missing
    value_counts = {f: Counter() for f in match_fields}
    pair_counts: Counter = Counter()
    nulls: Counter = Counter()
    lens: dict[str, list[int]] = {h: [] for h in headers}
    created: list[str] = []
    coords = n = 0
    cov = CoverageReport()
    for row in iter_rows(path):
        n += 1
        if n > max_rows:
            break
        for h in headers:
            v = row.get(h)
            if v in (None, ""):
                nulls[h] += 1
            elif isinstance(v, str) and len(lens[h]) < 2000:
                lens[h].append(len(v))
        for f in match_fields:
            v = cols.get(row, f)
            if v is not None:
                value_counts[f][str(v)] += 1
        if len(match_fields) >= 2:
            pair_counts[tuple(str(cols.get(row, f)) for f in match_fields[:2])] += 1
        ts = parse_ts(cols.get(row, "created_at"))
        if ts:
            created.append(ts)
        if parse_coord(cols.get(row, "latitude"), -90, 90) is not None and parse_coord(cols.get(row, "longitude"), -180, 180) is not None:
            coords += 1
        if mapping is not None:
            res = mapping.map(**{f: cols.get(row, f) for f in match_fields})
            cov.add(res, " | ".join(str(cols.get(row, f)) for f in match_fields))
    n = min(n, max_rows)
    free_text = sorted(((h, round(sum(v) / len(v), 1)) for h, v in lens.items() if len(v) >= 20 and sum(v) / len(v) > 80),
                       key=lambda x: -x[1])
    return {
        "file": path.name, "rows_profiled": n, "headers": headers,
        "resolved_columns": {k: v for k, v in cols.map.items() if v},
        "unresolved_aliases": sorted(k for k, v in cols.map.items() if v is None),
        "null_rate": {h: round(nulls[h] / max(n, 1), 4) for h in headers},
        "date_range": [min(created), max(created)] if created else None,
        "coordinate_coverage": round(coords / max(n, 1), 4),
        "top_values": {f: c.most_common(top) for f, c in value_counts.items()},
        "top_value_pairs": [[list(k), v] for k, v in pair_counts.most_common(top)],
        "candidate_free_text_columns": [{"column": h, "mean_length": m} for h, m in free_text],
        "free_text_note": ("Columns with long average strings may contain narrative text OR agency resolution text. Inspect samples "
                           "manually; only genuine citizen-written text may be used as classifier input (text_origin=citizen_narrative)."),
        "draft_mapping_coverage": cov.to_dict(top) if mapping is not None else None,
    }
