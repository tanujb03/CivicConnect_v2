"""Prepare an externally downloaded dataset into the canonical schema (never touches ai/inference)."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from ai.inference.config import load_taxonomy
from ai.training.src.io_utils import git_sha, sha256_file

from .adapters.bmc_mumbai import BMCMumbaiAdapter
from .adapters.chicago311 import Chicago311Adapter
from .adapters.detection import DetectionDatasetAdapter, load_class_names
from .adapters.nyc311 import NYC311Adapter
from .adapters.rdd2022 import RDD2022Adapter
from .card_schema import SourceCard
from .column_roles import TaskPolicy
from .errors import DataSourceError
from .image_profile import VIDEO
from .leakage import audit_task, censoring_report, split_straddle, views_clean
from .mapping import DepartmentMapping, MappingTable
from .splits import group_holdout, hash_fraction, time_holdout

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
                check_images: bool = False, include_unannotated: bool = False, max_images: int | None = None, retrieved_at: str | None = None,
                default_country: str | None = None, holdout_fraction: float = 0.0, holdout_seed: int = 0, block_size: int = 100) -> dict:
    """``holdout_countries`` holds out whole countries; ``holdout_fraction`` (single-country copies, e.g. India only) holds out whole
    index-block groups chosen by a seeded hash — never single frames. Block ids are a HEURISTIC (frame numbering is not verified to follow drive order)."""
    if holdout_countries and holdout_fraction:
        raise DataSourceError("choose either holdout_countries or holdout_fraction, not both")
    mapping = MappingTable.load(card.mapping_id)
    ad = RDD2022Adapter(card, mapping, retrieved_at=retrieved_at, default_country=default_country, block_size=block_size)
    recs = list(ad.iter_records(root, countries=countries, check_images=check_images, include_unannotated=include_unannotated, max_images=max_images))
    if holdout_countries:
        recs = group_holdout(recs, lambda r: r.country, holdout_countries)
    if holdout_fraction:
        recs = [r if (r.group_id is None or r.split_hint in ("test", "val"))
                else r.model_copy(update={"split_hint": "holdout" if hash_fraction(r.group_id, holdout_seed) < holdout_fraction else "train"}) for r in recs]
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
        "origin_verified": card.origin_verified, "identity_status": card.identity_status,
        "options": {"countries": sorted(countries or []), "holdout_countries": sorted(holdout_countries or []), "check_images": check_images,
                    "include_unannotated": include_unannotated, "max_images": max_images, "default_country": default_country,
                    "holdout_fraction": holdout_fraction, "holdout_seed": holdout_seed, "block_size": block_size},
        "split_straddle": split_straddle(recs, lambda r: r.group_id), "n_groups": len({r.group_id for r in recs if r.group_id}),
        "adapter_stats": ad.stats, "images_per_country": dict(per_country), "boxes_per_class": dict(cls),
        "images_with_no_boxes": sum(1 for r in recs if r.has_annotation and not r.boxes),
        "image_label_counts": dict(Counter(lab for r in recs for lab in r.image_labels)),
        "split_counts": dict(Counter(r.split_hint or "none" for r in recs)),
        "box_mapping_coverage": ad.coverage.to_dict(),
        "prepared_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git_sha": git_sha(),
        "redistribution": f"NOT permitted from this repository (licence {card.license.status}: {card.license.name}); keep outside git.",
        "required_citations": card.citation,
    }
    (out_dir / "PREPARE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def prepare_bmc(card: SourceCard, input_path: Path, out_dir: Path, *, role_map: dict | None = None, max_rows: int | None = None, sample_seed: int = 0,
                since: str | None = None, until: str | None = None, holdout_after: str | None = None, confirm_citizen_text: bool = False,
                row_index_ids: bool = False, resolution_unit: str | None = None, retrieved_at: str | None = None) -> dict:
    policy = TaskPolicy.load("bmc_mumbai")
    mapping, dept = MappingTable.load(card.mapping_id), DepartmentMapping.load("bmc_mumbai_departments")
    ad = BMCMumbaiAdapter(card, mapping, dept, policy, retrieved_at=retrieved_at, role_map=role_map, confirm_citizen_text=confirm_citizen_text,
                          row_index_ids=row_index_ids, resolution_unit=resolution_unit)
    recs = list(ad.iter_records(input_path, max_rows=max_rows, sample_seed=sample_seed, since=since, until=until))
    if holdout_after:
        recs = time_holdout(recs, holdout_after)
    out_dir.mkdir(parents=True, exist_ok=True)
    n = _write_jsonl(out_dir / "records.jsonl", recs)
    confirmations = {"description_is_citizen_text"} if confirm_citizen_text else set()
    tasks = {}
    for t in policy.tasks:
        ok, why = policy.runnable(t, set(ad.resolution.columns), confirmations)  # type: ignore[union-attr]
        tasks[t] = {"status": policy.tasks[t].status, "runnable": ok, "reasons": why,
                    "audit": audit_task(recs, policy, t) if ok and policy.tasks[t].leakage_checks else None}
    created = sorted(r.created_at for r in recs if r.created_at)
    manifest = {
        "schema": "canonical-data/1", "source_id": card.id, "kind": "case_records", "records": n,
        "input_file": Path(input_path).name, "input_sha256": sha256_file(Path(input_path)), "card_fingerprint": card.fingerprint(),
        "license_verified": card.license_verified, "license_status": card.license.status, "origin_verified": card.origin_verified,
        "source_kind": card.kind, "origin_status": card.origin_status, "origin_notes": card.origin_notes, "identity_status": card.identity_status,
        "mapping": {"id": mapping.mapping_id, "version": mapping.version, "fingerprint": mapping.fingerprint(), "status": mapping.raw["status"]},
        "department_mapping": {"id": dept.mapping_id, "version": dept.version, "status": dept.raw["status"]},
        "column_policy": {"version": policy.spec.policy_version, "status": policy.spec.status},
        "taxonomy_version": load_taxonomy().version,
        "columns": ad.summary(),
        "options": {"max_rows": max_rows, "sample_seed": sample_seed, "since": since, "until": until, "holdout_after": holdout_after,
                    "confirm_citizen_text": confirm_citizen_text, "row_index_ids": row_index_ids, "resolution_unit": resolution_unit,
                    "role_map_columns": sorted(role_map or {})},
        "adapter_stats": ad.stats, "coverage": ad.coverage.to_dict(),
        "text_origin_counts": dict(Counter(r.text_origin for r in recs)), "split_counts": dict(Counter(r.split_hint or "none" for r in recs)),
        "citizen_narrative_text_available": any(r.text_origin == "citizen_narrative" for r in recs),
        "task_status": tasks, "views_clean": views_clean(recs, policy), "censoring": censoring_report(recs),
        "date_range": [created[0], created[-1]] if created else None,
        "prepared_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git_sha": git_sha(),
        "redistribution": "NOT permitted from this repository (Kaggle competition rules not read; see source card); keep outside git.",
    }
    (out_dir / "PREPARE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def prepare_images(card: SourceCard, root: Path, out_dir: Path, *, fmt: str, class_names_file: Path | None = None, group_by: str = "dir",
                   group_regex: str | None = None, block_size: int = 100, label_from: str = "parent", holdout_fraction: float = 0.0,
                   holdout_seed: int = 0, max_images: int | None = None, retrieved_at: str | None = None, countries: set[str] | None = None,
                   default_country: str | None = None, split_from_path: bool = False, holdout_splits: tuple[str, ...] = ("val", "test")) -> dict:
    """Layout-agnostic image preparation (VOC / YOLO / COCO / folder labels). Also used for RDD2020/RDD2022 copies whose directory layout or
    annotation format differs from the official distribution (the RDD-specific adapter assumes the official layout)."""
    if card.adapter not in ("detection", "rdd2022"):
        raise DataSourceError(f"{card.id} does not use an image-detection adapter")
    if split_from_path and holdout_fraction:
        raise DataSourceError("choose either split_from_path (source splits) or holdout_fraction (group hash), not both")
    mapping = MappingTable.load(card.mapping_id)
    names = load_class_names(class_names_file) if class_names_file else None
    ad = DetectionDatasetAdapter(card, mapping, fmt=fmt, class_names=names, group_by=group_by, group_regex=group_regex, block_size=block_size,
                                 label_from=label_from, retrieved_at=retrieved_at, countries=countries, default_country=default_country,
                                 split_from_path=split_from_path, holdout_splits=holdout_splits)
    recs = list(ad.iter_records(root, max_images=max_images))
    if holdout_fraction:
        if group_by == "none":
            raise DataSourceError("a holdout needs a group rule (dir/regex/block): random frame splits leak near-identical frames")
        recs = [r if r.group_id is None else r.model_copy(update={"split_hint": "holdout" if hash_fraction(r.group_id, holdout_seed) < holdout_fraction else "train"}) for r in recs]
    out_dir.mkdir(parents=True, exist_ok=True)
    n = _write_jsonl(out_dir / "records.jsonl", recs)
    groups = Counter(r.group_id for r in recs if r.group_id)
    pos = sum(1 for r in recs if "roads/pothole" in r.image_labels)
    manifest = {
        "schema": "canonical-data/1", "source_id": card.id, "kind": "image_records", "records": n, "format": fmt, "dataset_root_name": Path(root).name,
        "card_fingerprint": card.fingerprint(), "license_verified": card.license_verified, "license_status": card.license.status, "origin_verified": card.origin_verified,
        "identity_status": card.identity_status, "mapping": {"id": mapping.mapping_id, "version": mapping.version, "fingerprint": mapping.fingerprint(), "status": mapping.raw["status"]},
        "taxonomy_version": load_taxonomy().version,
        "options": {"group_by": group_by, "group_regex": group_regex, "block_size": block_size, "label_from": label_from, "holdout_fraction": holdout_fraction,
                    "holdout_seed": holdout_seed, "class_names_file": Path(class_names_file).name if class_names_file else None, "max_images": max_images,
                    "countries": sorted(countries or []), "default_country": default_country, "split_from_path": split_from_path,
                    "holdout_splits": list(holdout_splits) if split_from_path else None},
        "adapter_stats": ad.stats, "box_or_label_mapping_coverage": ad.coverage.to_dict(),
        "n_groups": len(groups), "largest_groups": groups.most_common(5), "images_without_group": sum(1 for r in recs if r.group_id is None),
        "split_counts": dict(Counter(r.split_hint or "none" for r in recs)), "split_straddle": split_straddle(recs, lambda r: r.group_id),
        "source_label_counts": dict(Counter(lab for r in recs for lab in r.source_labels)), "image_label_counts": dict(Counter(lab for r in recs for lab in r.image_labels)),
        "pothole_positive_share": round(pos / max(n, 1), 4),
        "positive_only_warning": "every image is a pothole image: precision is not meaningful without negatives" if n and pos / n >= 0.99 else None,
        "n_videos_in_root": sum(1 for p in Path(root).rglob("*") if p.suffix.lower() in VIDEO),
        "prepared_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git_sha": git_sha(),
        "redistribution": "NOT permitted from this repository (licence unverified); keep outside git. Images are referenced, never copied.",
        "required_citations": card.citation,
    }
    (out_dir / "PREPARE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest
