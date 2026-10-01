"""Explicit, versioned mapping layer: external labels -> CivicConnect taxonomy.

Nothing is auto-mapped. A rule maps a *specific* source label to a taxonomy category (and
optionally subcategory); everything else is ``unmapped`` or an explicit ``out_of_scope``.
Mapping tables are DRAFT artifacts: coverage reports and ``profile`` output are used to verify
and extend them against the real files before any model claim.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ai.inference.config import Taxonomy, load_taxonomy

from .errors import MappingError

MAPPINGS_DIR = Path(__file__).parent / "mappings"


def _norm(v: Any) -> str:
    return " ".join(str(v if v is not None else "").casefold().split())


@dataclass(frozen=True)
class MappingResult:
    status: str                       # exact | category_only | out_of_scope | unmapped
    category: str | None = None
    subcategory: str | None = None
    rule_id: str | None = None
    confidence: str | None = None


@dataclass
class MappingTable:
    raw: dict
    taxonomy: Taxonomy
    rules: list[dict] = field(default_factory=list)

    @property
    def mapping_id(self) -> str:
        return self.raw["mapping_id"]

    @property
    def version(self) -> str:
        return self.raw["mapping_version"]

    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(self.raw, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    @classmethod
    def from_dict(cls, raw: dict, taxonomy: Taxonomy | None = None) -> "MappingTable":
        t = taxonomy or load_taxonomy()
        table = cls(raw=raw, taxonomy=t, rules=list(raw["rules"]))
        table.validate()
        return table

    @classmethod
    def load(cls, mapping_id: str, taxonomy: Taxonomy | None = None, mappings_dir: Path = MAPPINGS_DIR) -> "MappingTable":
        path = mappings_dir / f"{mapping_id}.v1.json"
        if not path.is_file():
            raise MappingError(f"mapping table not found: {path}")
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")), taxonomy)

    def validate(self) -> None:
        ids = [r["id"] for r in self.rules]
        if len(ids) != len(set(ids)):
            raise MappingError("duplicate rule ids")
        fields = set(self.raw["match_fields"])
        for r in self.rules:
            if not set(r["when"]) <= fields:
                raise MappingError(f"rule {r['id']} matches on fields outside match_fields {sorted(fields)}")
            if r.get("out_of_scope"):
                if r.get("category") or r.get("subcategory"):
                    raise MappingError(f"rule {r['id']}: out_of_scope rules cannot carry a label")
                continue
            cat, sub = r.get("category"), r.get("subcategory")
            if cat not in self.taxonomy.categories:
                raise MappingError(f"rule {r['id']}: unknown category {cat!r}")
            if sub is not None and not self.taxonomy.is_valid_pair(cat, sub):
                raise MappingError(f"rule {r['id']}: {cat}/{sub} is not in taxonomy {self.taxonomy.version}")
            for k, cond in r["when"].items():
                if isinstance(cond, dict) and not (set(cond) <= {"equals", "contains", "regex", "startswith"}):
                    raise MappingError(f"rule {r['id']}: unsupported condition on {k}")
                if isinstance(cond, dict) and "regex" in cond:
                    re.compile(cond["regex"])

    @staticmethod
    def _match(cond: Any, value: Any) -> bool:
        v = _norm(value)
        if isinstance(cond, str):
            return v == _norm(cond)
        if "equals" in cond and v != _norm(cond["equals"]):
            return False
        if "contains" in cond and _norm(cond["contains"]) not in v:
            return False
        if "startswith" in cond and not v.startswith(_norm(cond["startswith"])):
            return False
        if "regex" in cond and not re.search(cond["regex"], v):
            return False
        return True

    def map(self, **source_fields: Any) -> MappingResult:
        """First matching rule wins (order = specificity). Missing fields never match a condition."""
        for r in self.rules:
            if all(k in source_fields and source_fields[k] is not None and self._match(c, source_fields[k])
                   for k, c in r["when"].items()):
                if r.get("out_of_scope"):
                    return MappingResult("out_of_scope", rule_id=r["id"], confidence=r.get("confidence"))
                sub = r.get("subcategory")
                return MappingResult("exact" if sub else "category_only", r["category"], sub, r["id"], r.get("confidence"))
        return MappingResult("unmapped")

    def department_for(self, res: MappingResult) -> str | None:
        return self.taxonomy.department_for(res.category, res.subcategory) if res.category else None


@dataclass
class CoverageReport:
    """Aggregates how a real label space lands in our taxonomy (reported with every preparation)."""

    total: int = 0
    by_status: Counter = field(default_factory=Counter)
    by_label: Counter = field(default_factory=Counter)
    unmapped_source: Counter = field(default_factory=Counter)
    out_of_scope_source: Counter = field(default_factory=Counter)

    def add(self, res: MappingResult, source_label: str) -> None:
        self.total += 1
        self.by_status[res.status] += 1
        if res.category:
            self.by_label[f"{res.category}/{res.subcategory or '*'}"] += 1
        elif res.status == "unmapped":
            self.unmapped_source[source_label] += 1
        elif res.status == "out_of_scope":
            self.out_of_scope_source[source_label] += 1

    def to_dict(self, top: int = 25) -> dict:
        n = max(self.total, 1)
        return {
            "total": self.total,
            "share": {k: round(v / n, 4) for k, v in sorted(self.by_status.items())},
            "counts": dict(sorted(self.by_status.items())),
            "mapped_to_subcategory_share": round(self.by_status.get("exact", 0) / n, 4),
            "mapped_any_share": round((self.by_status.get("exact", 0) + self.by_status.get("category_only", 0)) / n, 4),
            "by_label": dict(self.by_label.most_common()),
            "top_unmapped_source_labels": self.unmapped_source.most_common(top),
            "top_out_of_scope_source_labels": self.out_of_scope_source.most_common(top),
        }
