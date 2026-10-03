"""Provenance of gold (evaluation-only) text rows, and how reports must label them.

A gold row is exactly one of: ``human`` (explicitly marked as written by a person), ``llm_authored_<family>`` (e.g. ``llm_authored_claude``) or ``unspecified``.
Nothing is ever defaulted to ``human``: a row whose provenance is missing, unrecognised or contradictory is ``unspecified``, treated as NOT human
(``synthetic`` True) and reported in its own block. Blocks of different provenance are never pooled. Pure functions, no heavy imports (also used by the corpus builder).
"""
from __future__ import annotations

import re
from collections import Counter

HUMAN = "human"
UNSPECIFIED = "unspecified"
LLM_PREFIX = "llm_authored_"
_LLM = re.compile(r"\bllm_authored_[a-z0-9_]+\b")

CLAIMS = {
    HUMAN: "human-written by the team: the only yardstick for wording realism; still not a measurement on real citizen reports.",
    UNSPECIFIED: "provenance NOT specified: do not describe this set as human-written; treat it as unverified.",
}
CLAIM_LLM = "LLM-authored ({family}), not human text: a cross-family sanity check only, never a real-world accuracy claim and never a substitute for a human gold set."


def normalize(value: object) -> str | None:
    """A recognised provenance value, else None."""
    v = str(value or "").strip().lower()
    return v if v == HUMAN or _LLM.fullmatch(v) else None


def read_provenance(column: object, notes: object) -> tuple[str, str]:
    """(provenance, source) of one CSV row: the ``provenance`` column wins, else an ``llm_authored_*`` marker in notes, else ``unspecified``.
    source: column | notes | none | column_unrecognized | conflict (column and notes name different provenances)."""
    marker = _LLM.search(str(notes or "").lower())
    marker = marker.group(0) if marker else None
    if str(column or "").strip():
        col = normalize(column)
        if col is None:
            return UNSPECIFIED, "column_unrecognized"
        return (UNSPECIFIED, "conflict") if marker and marker != col else (col, "column")
    return (marker, "notes") if marker else (UNSPECIFIED, "none")


def label_origin(provenance: str) -> str:
    return "team_authored" if provenance == HUMAN else provenance


def is_synthetic(provenance: str) -> bool:
    """Only an explicitly human row is not synthetic."""
    return provenance != HUMAN


def row_provenance(row: dict) -> str:
    """Provenance of a gold.jsonl row. Rows from corpora built before provenance existed have none (their ``team_authored`` was a default): ``unspecified``."""
    return normalize(row.get("provenance")) or UNSPECIFIED


def block_name(provenance: str, n: int) -> str:
    return f"gold[{provenance}, n={n}]"


def claim(provenance: str) -> str:
    return CLAIM_LLM.format(family=provenance[len(LLM_PREFIX):]) if provenance.startswith(LLM_PREFIX) else CLAIMS[provenance]


def split_by_provenance(rows: list[dict]) -> dict[str, list[dict]]:
    """One evaluation set per provenance, keyed ``gold[<provenance>, n=<rows>]``. Different provenances are never pooled."""
    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(row_provenance(r), []).append(r)
    return {block_name(p, len(rs)): rs for p, rs in sorted(by.items())}


def block_meta(rows: list[dict]) -> dict:
    """Labels for one metric block (rows of a single provenance)."""
    prov = {row_provenance(r) for r in rows}
    if len(prov) != 1:
        raise ValueError(f"a gold metric block must hold one provenance, got {sorted(prov)}")
    p = prov.pop()
    return {"provenance": p, "human_written": p == HUMAN, "claim": claim(p)}


def count_by_provenance(rows: list[dict]) -> dict:
    """Manifest block: row counts by provenance (and by provenance x language)."""
    by = Counter(r["provenance"] for r in rows)
    by_lang: dict[str, Counter] = {}
    for r in rows:
        by_lang.setdefault(r["provenance"], Counter())[r["language"]] += 1
    return {"by_provenance": dict(sorted(by.items())), "by_provenance_language": {p: dict(sorted(c.items())) for p, c in sorted(by_lang.items())},
            "human_rows": by.get(HUMAN, 0), "note": "only rows marked human are team-written; llm_authored_* and unspecified rows are never reported as human gold"}
