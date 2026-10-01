"""Prepare an externally downloaded dataset into the canonical schema (never touches ai/inference)."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from ai.inference.config import load_taxonomy
from ai.training.src.io_utils import git_sha, sha256_file

from .adapters.chicago311 import Chicago311Adapter
from .adapters.nyc311 import NYC311Adapter
from .adapters.rdd2022 import RDD2022Adapter
from .card_schema import SourceCard
from .errors import DataSourceError
from .mapping import MappingTable
from .splits import group_holdout, time_holdout

TABULAR = {"nyc311": NYC311Adapter, "chicago311": Chicago311Adapter}


def _write_jsonl(path: Path, models) -> int:
    n = 0
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for m in models:
            fh.write(m.model_dump_json() + "\n")
            n += 1
    return n


def prepare_tabular(card: SourceCard, input_path: Path, out_dir: Path, *, max_rows: int | None = None, sample_seed: int = 0,
                    since: str | None = None, until: str | None = None, holdout_after: str | None = None,
                    include_category_text: bool = False, exclude_legacy: bool = False, retrieved_at: str | None = None) -> dict:
    if card.id not in TABULAR:
        raise DataSourceError(f"no tabular adapter for {card.id}")
    mapping = MappingTable.load(card.mapping_id)
    ad = TABULAR[card.id](card, mapping, retrieved_at=retrieved_at, include_category_text=include_category_text, exclude_legacy=exclude_legacy)
    recs = list(ad.iter_records(input_path, max_rows=max_rows, sample_seed=sample_seed, since=since, until=until))
    if holdout_after:
        recs = time_holdout(recs, holdout_after)
    out_dir.mkdir(parents=True, exist_ok=True)
    n = _write_jsonl(out_dir / "records.jsonl", recs)
    created = sorted(r.created_at for r in recs if r.created_at)
    manifest = {
        "schema": "canonical-data/1", "source_id": card.id, "kind": "case_records", "records": n,
        "input_file": Path(input_path).name, "input_sha256": sha256_file(Path(input_path)),
        "card_fingerprint": card.fingerprint(), "license_verified": card.license_verified, "license_status": card.license.status,
        "mapping": {"id": mapping.mapping_id, "version": mapping.version, "fingerprint": mapping.fingerprint(),
                    "status": mapping.raw["status"]},
        "taxonomy_version": load_taxonomy().version,
        "options": {"max_rows": max_rows, "sample_seed": sample_seed, "since": since, "until": until, "holdout_after": holdout_after,
                    "include_category_text": include_category_text, "exclude_legacy": exclude_legacy},
        "adapter_stats": ad.stats,
        "coverage": ad.coverage.to_dict(),
        "text_origin_counts": dict(Counter(r.text_origin for r in recs)),
        "split_counts": dict(Counter(r.split_hint or "none" for r in recs)),
        "duplicate_flag_counts": dict(Counter(str(r.duplicate_flag) for r in recs)),
        "date_range": [created[0], created[-1]] if created else None,
        "citizen_narrative_text_available": any(r.text_origin == "citizen_narrative" for r in recs),
        "prepared_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git_sha": git_sha(),
        "redistribution": "NOT permitted from this repository (see source card); keep outside git.",
    }
    (out_dir / "PREPARE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def prepare_rdd(card: SourceCard, root: Path, out_dir: Path, *, countries: set[str] | None = None, holdout_countries: set[str] | None = None,
                check_images: bool = False, include_unannotated: bool = False, max_images: int | None = None, retrieved_at: str | None = None) -> dict:
    mapping = MappingTable.load(card.mapping_id)
    ad = RDD2022Adapter(card, mapping, retrieved_at=retrieved_at)
    recs = list(ad.iter_records(root, countries=countries, check_images=check_images, include_unannotated=include_unannotated, max_images=max_images))
    if holdout_countries:
        recs = group_holdout(recs, lambda r: r.country, holdout_countries)
    out_dir.mkdir(parents=True, exist_ok=True)
    n = _write_jsonl(out_dir / "records.jsonl", recs)
    per_country = Counter(r.country or "unknown" for r in recs)
    cls = Counter(b.class_code for r in recs for b in r.boxes)
    manifest = {
        "schema": "canonical-data/1", "source_id": card.id, "kind": "image_records", "records": n, "dataset_root_name": Path(root).name,
        "card_fingerprint": card.fingerprint(), "license_verified": card.license_verified, "license_status": card.license.status,
        "license_conflicts": card.license.conflicts,
        "mapping": {"id": mapping.mapping_id, "version": mapping.version, "fingerprint": mapping.fingerprint(), "status": mapping.raw["status"]},
        "taxonomy_version": load_taxonomy().version,
        "options": {"countries": sorted(countries or []), "holdout_countries": sorted(holdout_countries or []), "check_images": check_images,
                    "include_unannotated": include_unannotated, "max_images": max_images},
        "adapter_stats": ad.stats, "images_per_country": dict(per_country), "boxes_per_class": dict(cls),
        "images_with_no_boxes": sum(1 for r in recs if r.has_annotation and not r.boxes),
        "image_label_counts": dict(Counter(lab for r in recs for lab in r.image_labels)),
        "split_counts": dict(Counter(r.split_hint or "none" for r in recs)),
        "box_mapping_coverage": ad.coverage.to_dict(),
        "prepared_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git_sha": git_sha(),
        "redistribution": "NOT permitted from this repository (see source card; licence unresolved BY vs BY-SA); keep outside git.",
        "required_citations": card.citation,
    }
    (out_dir / "PREPARE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest
