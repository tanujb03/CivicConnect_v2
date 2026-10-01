"""Profile an externally downloaded tabular file BEFORE trusting any mapping.

Answers the questions the mapping tables and source cards leave open: which columns exist, what the
real category/descriptor values are, how much of the file the draft mapping covers, whether coordinates
and timestamps are usable, and -- importantly -- whether ANY column looks like free-text narrative.
"""
from __future__ import annotations

from collections import Counter, defaultdict
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


def profile_bmc(path: Path, policy, role_map: dict | None, mapping, dept_mapping, *, max_rows: int = 300_000, top: int = 40) -> dict:
    """Role-based pre-flight for the BMC file: which columns were claimed, which are unclassified (default-denied),
    the real value space, mapping coverage, free-text candidates, target determinism and which tasks are runnable.
    Values of PII and sensitive-attribute columns are never read."""
    from .leakage import VACUOUS_PURITY  # local import: leakage imports canonical, profile is a leaf

    headers = sniff_headers(path)
    res = policy.classify_headers(headers, role_map)
    skip_cols = set(res.pii_ignored) | set(res.sensitive_ignored)
    cols = res.columns
    top_vals = {r: Counter() for r in ("source_category", "source_subcategory", "department", "severity", "priority", "filing_channel", "ward", "status")}
    nulls: Counter = Counter()
    lens: dict[str, list[int]] = {h: [] for h in headers if h not in skip_cols}
    created: list[str] = []
    coords = n = in_bbox = closed = 0
    cov = CoverageReport()
    dept_cov: Counter = Counter()
    det: dict[str, dict] = {"department": defaultdict(Counter), "severity": defaultdict(Counter), "priority": defaultdict(Counter)}
    date_ok = date_n = 0
    for row in iter_rows(path):
        n += 1
        if n > max_rows:
            break
        for h in lens:
            v = row.get(h)
            if v in (None, ""):
                nulls[h] += 1
            elif isinstance(v, str) and len(lens[h]) < 2000:
                lens[h].append(len(v))

        def g(role, row=row):
            c = cols.get(role)
            if c is None or c in skip_cols:
                return None
            v = row.get(c)
            return v.strip() if isinstance(v, str) and v.strip() else (None if isinstance(v, str) else v)
        for r, ctr in top_vals.items():
            v = g(r)
            if v is not None:
                ctr[str(v)] += 1
        ts = g("created_at")
        date_n += ts is not None
        p = parse_ts(ts)
        if p:
            created.append(p)
            date_ok += 1
        lat, lon = parse_coord(g("latitude"), -90, 90), parse_coord(g("longitude"), -180, 180)
        if lat is not None and lon is not None:
            coords += 1
            in_bbox += (18.85 <= lat <= 19.35 and 72.75 <= lon <= 73.05)
        closed += g("closed_at") is not None
        sc = g("source_category")
        if sc is not None:
            m = mapping.map(category=sc, subcategory=g("source_subcategory"))
            cov.add(m, str(sc))
            for tgt in det:
                tv = g(tgt)
                if tv is not None:
                    det[tgt][str(sc)][str(tv)] += 1
        d = g("department")
        if d is not None:
            dept_cov[dept_mapping.map(str(d)) or "UNMAPPED"] += 1
    n = min(n, max_rows)
    purity = {}
    for tgt, groups in det.items():
        tot = sum(sum(c.values()) for c in groups.values())
        if tot:
            pur = sum(c.most_common(1)[0][1] for c in groups.values()) / tot
            purity[tgt] = {"rows": tot, "purity_given_source_category": round(pur, 4), "vacuous_as_target": pur >= VACUOUS_PURITY}
    free_text = sorted(((h, round(sum(v) / len(v), 1)) for h, v in lens.items() if len(v) >= 20 and sum(v) / len(v) > 60), key=lambda x: -x[1])
    runnable = {t: dict(zip(("runnable", "reasons"), policy.runnable(t, set(cols)))) for t in policy.tasks}
    return {
        "file": path.name, "rows_profiled": n, "headers": headers,
        "resolved_roles": cols, "unclassified_columns_default_denied": res.unclassified,
        "pii_columns_never_read": res.pii_ignored, "sensitive_columns_never_read": res.sensitive_ignored,
        "missing_roles_of_interest": sorted(r for r in ("source_category", "created_at", "ward", "latitude", "longitude", "department", "severity", "priority", "closed_at", "status",
                                                        "description", "duplicate_flag") if r not in cols),
        "null_rate": {h: round(nulls[h] / max(n, 1), 4) for h in lens},
        "created_at_parse_rate": round(date_ok / max(date_n, 1), 4) if date_n else None, "date_range": [min(created), max(created)] if created else None,
        "coordinate_coverage": round(coords / max(n, 1), 4), "coordinates_inside_mumbai_bbox": round(in_bbox / max(coords, 1), 4) if coords else None,
        "resolved_share_closed_at_present": round(closed / max(n, 1), 4) if "closed_at" in cols else None,
        "top_values": {k: v.most_common(top) for k, v in top_vals.items() if v},
        "draft_category_mapping_coverage": cov.to_dict(top), "draft_department_mapping_share": {k: round(v / max(sum(dept_cov.values()), 1), 4) for k, v in dept_cov.items()},
        "target_determinism_given_source_category": purity,
        "candidate_free_text_columns": [{"column": h, "mean_length": m} for h, m in free_text],
        "free_text_note": ("A long-string column may be citizen text, an agency remark, or generated text. Inspect samples by hand; confirm with --confirm-citizen-text only if it is citizen-written "
                           "AND does not echo the label. Resolution remarks are never stored."),
        "tasks_runnable_given_columns": runnable,
    }
