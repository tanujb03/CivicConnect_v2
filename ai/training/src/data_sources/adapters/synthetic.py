"""Wrap the project's synthetic rows in the canonical schema (so hybrid pipelines carry provenance)."""
from __future__ import annotations

from ..canonical import CaseRecord, Provenance

_LABEL_MAP = {"synthetic-civic/1.0": "synthetic-civic/1.0"}


def synthetic_provenance(generator_version: str, record_id: str | None) -> Provenance:
    return Provenance(kind="synthetic", source_id="synthetic_civic", source_dataset=f"CivicConnect synthetic reports ({generator_version})",
                      source_version=generator_version, source_record_id=record_id, license_id="project-owned", license_verified=True,
                      label_origin="synthetic_template")


def from_synthetic_row(row: dict) -> CaseRecord:
    return CaseRecord(
        record_id=f"synthetic_civic:{row['id']}", provenance=synthetic_provenance(row.get("generator_version", "unknown"), row["id"]),
        text=row["text"], text_origin="citizen_narrative", language=row.get("language"),
        category=row["category"], subcategory=row["subcategory"], department=row.get("department"),
        mapping_status="not_applicable", split_hint=row.get("split") if row.get("split") in ("train", "val", "test") else None)
