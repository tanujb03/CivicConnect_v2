"""Kaggle-in-place execution of the CivicConnect real-data framework, one dataset at a time.

Datasets are read where Kaggle mounts them (``/kaggle/input/...``): nothing is downloaded or copied, nothing is
written to the repository, and only small aggregate reports are meant to leave the notebook. Each dataset runs
independently — attach one, several or all of them — and a missing or unusable dataset yields a precise
``NOT_ATTACHED`` / ``NEEDS_CONFIG`` / ``NEEDS_TERMS`` result, not a stack trace.

Stages (BMC synthetic civic data):  card → locate → profile (columns/roles) → role validation → mapping validation → terms gate →
                                    prepare (time holdout) → leakage audit → synthetic-track evaluation → report
Stages (image datasets):            card → locate → profile-images → annotation format/class names (never guessed) → terms gate →
                                    prepare (group-safe holdout) → mapping validation → image/annotation/duplicate/group audits →
                                    real_holdout readiness (licence, size, straddle, negatives) → optional provider evaluation → report

Nothing here calls a model or provider unless ``run_provider_eval`` is set AND credentials exist; provider failures never block profiling.
Real and synthetic results are never pooled: BMC is third-party SYNTHETIC data (``synthetic`` track / ``descriptive`` statistics),
the image datasets are real (``real_holdout`` track).
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai.evaluation.provenance import MIN_REAL_N, build_provenance, claims_for
from ai.training.src.io_utils import read_jsonl

from . import prepare as prep
from .adapters.detection import load_class_names
from .canonical import ImageRecord
from .card_schema import SourceCard, check_terms, load_card
from .column_roles import TaskPolicy
from .errors import DataSourceError, TermsNotAccepted
from .image_audit import annotation_audit, group_audit, image_files_audit, video_frame_relationships
from .image_profile import profile_image_dataset
from .kaggle_inputs import SPECS, DatasetSpec, Location, describe_inputs, input_root, locate, pick_tabular_file
from .mapping import DepartmentMapping, MappingTable
from .paths import ensure_safe_output
from .profile import profile_bmc

STATUSES = ("OK", "PARTIAL", "NEEDS_CONFIG", "NEEDS_TERMS", "NOT_ATTACHED", "BLOCKED", "FAILED")
IMAGE_IDS = ("mumbai_nashik_road_surface", "rdd2022", "rdd2020", "bharatpothole")
ORDER = ("bmc_mumbai", *IMAGE_IDS)                         # execution/report order; no dataset depends on another
BMC_EVAL_TASKS = ("taxonomy_coverage", "resolution_time_prior", "recurrence_hotspot", "routing_agreement", "triage_priority_prior")
NEVER_BUNDLED = ("records.jsonl", "pairs.jsonl", "raw.jsonl")


@dataclass
class RunConfig:
    work_dir: Path = Path("/kaggle/working")
    input_root: Path | None = None
    accept_terms: list[str] = field(default_factory=list)        # dataset ids whose terms YOU have read and accept
    ack_unverified_license: bool = False                         # proceed locally while a licence is still UNVERIFIED (results must not be published)
    paths: dict[str, str] = field(default_factory=dict)          # dataset id -> mount/dir override
    files: dict[str, str] = field(default_factory=dict)          # tabular dataset id -> data file override
    # --- BMC (synthetic) ---
    role_map: dict[str, str] = field(default_factory=dict)       # {column: role} from the data dictionary
    row_index_ids: bool = False
    resolution_unit: str | None = None
    bmc_max_rows: int | None = 200_000
    bmc_sample_seed: int = 0
    bmc_holdout_after: str | None = None                         # None => the last 20% of the profiled date range
    # --- image datasets: per-dataset annotation/group decisions (never guessed) ---
    image: dict[str, dict] = field(default_factory=dict)         # id -> {format, class_names_file, group_by, group_regex, block_size, label_from, holdout_fraction, holdout_seed, default_country}
    audit_max_files: int = 50_000
    audit_max_near_dup_images: int = 6000
    run_provider_eval: bool = False
    retrieved_at: str | None = None

    @property
    def out(self) -> Path:
        return ensure_safe_output(Path(self.work_dir) / "civic_real")


# ------------------------------------------------------------------------------------------------ helpers
def _stage(res: dict, name: str, status: str, detail: str | dict | list | None = None) -> dict:
    s = {"stage": name, "status": status, "detail": detail}
    res["stages"].append(s)
    return s


def _card_summary(card: SourceCard) -> dict:
    return {"id": card.id, "name": card.name, "kind": card.kind, "priority": card.priority, "licence_name": card.license.name, "licence_status": card.license.status,
            "licence_verified": card.license_verified, "licence_conflicts": card.license.conflicts, "origin_status": card.origin_status, "identity_status": card.identity_status,
            "review_status": card.review_status, "restrictions": card.restrictions, "supports": [s.capability for s in card.supports],
            "does_not_support": [g.capability for g in card.does_not_support], "mapping_id": card.mapping_id, "reference": card.reference, "landing_url": card.landing_url}


def _new(card: SourceCard, spec: DatasetSpec) -> dict:
    return {"dataset_id": card.id, "title": spec.title, "status": "OK", "evidence_class": "third_party_synthetic" if card.kind == "synthetic_third_party" else "real_public",
            "card": _card_summary(card), "stages": [], "next_steps": [], "artifacts": [], "real_world_claim_allowed": False}


def _terms(res: dict, card: SourceCard, cfg: RunConfig) -> bool:
    try:
        check_terms(card, accepted=cfg.accept_terms, ack_unverified=cfg.ack_unverified_license)
    except TermsNotAccepted as e:
        _stage(res, "terms_gate", "blocked", str(e).split("\n\n")[0])
        res["terms_summary"] = card.terms_summary()
        res["status"] = "NEEDS_TERMS"
        res["next_steps"].append(f"Read the terms above and the dataset's own terms page; then set ACCEPT_TERMS to include '{card.id}'"
                                 + ("" if card.license_verified else " and ACK_UNVERIFIED_LICENSE = True (the licence is UNVERIFIED: results must not be published)") + ".")
        return False
    _stage(res, "terms_gate", "ok", f"accepted {card.id}; licence {card.license.status}" + ("" if card.license_verified else " (acknowledged unverified: results must not be published)"))
    return True


def _write_json(path: Path, obj) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    return path


def _auto_holdout_date(date_range: list[str] | None) -> str | None:
    if not date_range or len(date_range) != 2:
        return None
    lo, hi = datetime.fromisoformat(date_range[0]), datetime.fromisoformat(date_range[1])
    return (lo + timedelta(seconds=(hi - lo).total_seconds() * 0.8)).date().isoformat()


def _finalize(res: dict) -> dict:
    """Overall status: the worst stage outcome that stopped the run, else PARTIAL when stages were skipped, else OK."""
    if res["status"] != "OK":
        return res
    bad = [s for s in res["stages"] if s["status"] == "failed"]
    blocked = [s for s in res["stages"] if s["status"] == "blocked"]
    if bad:
        res["status"] = "FAILED"
    elif blocked:
        res["status"] = "BLOCKED"
    elif any(s["status"] == "skipped" for s in res["stages"]):
        res["status"] = "PARTIAL"
    return res


# ------------------------------------------------------------------------------------------------ BMC (synthetic)
def run_bmc(cfg: RunConfig) -> dict:
    spec, card = SPECS["bmc_mumbai"], load_card("bmc_mumbai")
    res = _new(card, spec)
    d = cfg.out / "bmc_mumbai"
    _stage(res, "card_provenance", "ok", {"kind": card.kind, "origin_status": card.origin_status, "origin_notes": card.origin_notes,
                                          "licence": f"{card.license.status}: {card.license.name}"})
    loc = locate(spec, cfg.input_root, cfg.paths.get("bmc_mumbai"))
    res["location"] = loc.to_dict()
    if not loc.found:
        res["status"] = "NOT_ATTACHED"
        _stage(res, "locate", "blocked", loc.message)
        res["next_steps"].append(loc.message)
        return res
    _stage(res, "locate", "ok", {"path": str(loc.path), "how": loc.how, "tabular_files": loc.structure.get("tabular_files")})
    f, why = pick_tabular_file(loc, cfg.files.get("bmc_mumbai"))
    if f is None:
        res["status"] = "NEEDS_CONFIG"
        _stage(res, "select_data_file", "blocked", why)
        res["next_steps"].append(why)
        return res
    _stage(res, "select_data_file", "ok", f"{f.name} ({why})")
    policy, mapping, dept = TaskPolicy.load("bmc_mumbai"), MappingTable.load(card.mapping_id), DepartmentMapping.load("bmc_mumbai_departments")
    try:
        prof = profile_bmc(f, policy, cfg.role_map or None, mapping, dept, max_rows=cfg.bmc_max_rows or 300_000)
    except DataSourceError as e:
        res["status"] = "NEEDS_CONFIG"
        _stage(res, "profile_and_role_validation", "blocked", str(e))
        res["next_steps"].append(f"Fix the column-role assignment: {e}")
        return res
    _write_json(d / "profile.json", prof)
    res["artifacts"].append("bmc_mumbai/profile.json")
    required = [r for r in ("source_category", "created_at") if r not in prof["resolved_roles"]]
    if "complaint_id" not in prof["resolved_roles"] and not cfg.row_index_ids:
        required.append("complaint_id (or set row_index_ids=True)")
    _stage(res, "profile_and_role_validation", "blocked" if required else "ok", {
        "rows_profiled": prof["rows_profiled"], "headers": prof["headers"], "resolved_roles": prof["resolved_roles"],
        "unclassified_columns_default_denied": prof["unclassified_columns_default_denied"], "pii_columns_never_read": prof["pii_columns_never_read"],
        "sensitive_columns_never_read": prof["sensitive_columns_never_read"], "missing_required_roles": required, "missing_roles_of_interest": prof["missing_roles_of_interest"],
        "created_at_parse_rate": prof["created_at_parse_rate"], "date_range": prof["date_range"], "candidate_free_text_columns": prof["candidate_free_text_columns"]})
    if required:
        res["status"] = "NEEDS_CONFIG"
        res["next_steps"].append(f"Required roles not resolvable from the headers: {required}. Read the data dictionary and set ROLE_MAP = {{column: role}} "
                                 f"(roles: {sorted(policy.roles)}). Headers: {prof['headers']}")
        return res
    cov = prof["draft_category_mapping_coverage"]
    _stage(res, "mapping_validation", "ok" if not cov.get("counts", {}).get("unmapped") else "warning",
           {"coverage_share": cov.get("share"), "top_unmapped_source_labels": cov.get("top_unmapped_source_labels"), "top_out_of_scope": cov.get("top_out_of_scope_source_labels"),
            "department_mapping_share": prof["draft_department_mapping_share"], "note": "category list was user-reported and is a DRAFT mapping: extend it for any unmapped label and bump the version"})
    _stage(res, "determinism_preflight", "ok", prof["target_determinism_given_source_category"])
    if not _terms(res, card, cfg):
        return res
    holdout = cfg.bmc_holdout_after or _auto_holdout_date(prof["date_range"])
    try:
        man = prep.prepare_bmc(card, f, d / "prepared", role_map=cfg.role_map or None, max_rows=cfg.bmc_max_rows, sample_seed=cfg.bmc_sample_seed, holdout_after=holdout,
                               row_index_ids=cfg.row_index_ids, resolution_unit=cfg.resolution_unit, retrieved_at=cfg.retrieved_at)
    except DataSourceError as e:
        res["status"] = "NEEDS_CONFIG"
        _stage(res, "prepare", "blocked", str(e))
        res["next_steps"].append(str(e))
        return res
    _stage(res, "prepare", "ok", {"records": man["records"], "holdout_after": holdout, "holdout_rule": "time (most recent ~20% of the date range)" if not cfg.bmc_holdout_after else "time (operator date)",
                                  "split_counts": man["split_counts"], "adapter_stats": man["adapter_stats"], "coverage": man["coverage"]["share"],
                                  "text_origin_counts": man["text_origin_counts"], "source_kind": man["source_kind"]})
    res["artifacts"] += ["bmc_mumbai/prepared/PREPARE_MANIFEST.json"]
    tasks = man["task_status"]
    _stage(res, "leakage_audit", "ok" if man["views_clean"]["violations"] == [] else "failed", {
        "views_clean": man["views_clean"], "censoring": man["censoring"], "tasks": {t: {"status": v["status"], "runnable": v["runnable"], "why_not": v["reasons"],
                                                                                          "audit_passed": None if not v["audit"] else v["audit"]["passed"],
                                                                                          "blocking": None if not v["audit"] else v["audit"]["blocking"]} for t, v in tasks.items()}})
    # synthetic-track evaluation through the SAME harness as everything else (so claims/provenance blocks are identical)
    from ai.evaluation import run_eval
    results: dict[str, dict] = {}
    rec_path = d / "prepared" / "records.jsonl"
    for t in BMC_EVAL_TASKS:
        info = tasks.get(t)
        if info is not None and not info["runnable"]:
            results[t] = {"ran": False, "why": info["reasons"]}
            continue
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = run_eval.main(["--task", t, "--real-data", str(rec_path), "--out", str(d / "results"), "--name", f"bmc_mumbai_{t}"])
        out = {"ran": rc == 0, "exit_code": rc}
        if rc == 0:
            rep = json.loads((d / "results" / f"bmc_mumbai_{t}.json").read_text(encoding="utf-8"))
            leak = (rep["results"].get("leakage") or {}).get("blocking") if isinstance(rep["results"], dict) else None
            out.update({"track": rep["track"], "banner": rep["claims"]["banner"], "real_world_claim_allowed": rep["claims"]["real_world_accuracy_claim_allowed"],
                        "leakage_blocking": leak or [], "meaningful": not leak,
                        "report": f"bmc_mumbai/results/bmc_mumbai_{t}.json"})
            res["artifacts"].append(out["report"])
        else:
            out["error"] = buf.getvalue().strip()[-400:]
        results[t] = out
    _stage(res, "synthetic_evaluation", "ok", results)
    vac = [t for t, v in results.items() if v.get("leakage_blocking")]
    if vac:
        res["next_steps"].append(f"Tasks whose targets are (near-)deterministic given their allowed inputs — evaluation is vacuous, do not quote it: {vac}.")
    res["next_steps"].append("BMC is SYNTHETIC third-party data: none of these numbers is real-world evidence. Record the exact origin statement and the rules/licence text from the competition's own pages on the card.")
    return res


# ------------------------------------------------------------------------------------------------ image datasets
def _image_cfg(cfg: RunConfig, spec: DatasetSpec) -> dict:
    c = {"format": spec.default_format, "class_names_file": None, "group_by": None, "group_regex": None, "block_size": 100, "label_from": "parent",
         "holdout_fraction": 0.25 if spec.needs_xml_annotations else 0.0, "holdout_seed": 0, "default_country": spec.default_country}
    c.update({k: v for k, v in cfg.image.get(spec.id, {}).items() if v is not None})
    return c


def _readiness(card: SourceCard, recs: list[ImageRecord], extra: dict) -> dict:
    hold = [r for r in recs if r.split_hint in ("holdout", "test")]
    ann_hold = [r for r in hold if r.has_annotation]
    blockers: list[str] = []
    if not ann_hold:
        ng = extra.get("n_groups", 0)
        blockers.append(f"no annotated holdout images ({ng} group(s) in the prepared records): set a group rule and a holdout_fraction so whole videos/sequences are held out"
                        + ("; there are too few groups to form a holdout (lower block_size / use a finer group rule)" if ng < 4 else ""))
    if extra.get("straddling_groups"):
        blockers.append(f"{extra['straddling_groups']} group(s) straddle train and holdout")
    if extra.get("cross_split_near_duplicate_pairs"):
        blockers.append(f"{extra['cross_split_near_duplicate_pairs']} near-duplicate pair(s) span train and holdout (frame leakage)")
    if extra.get("cross_split_exact_duplicate_clusters"):
        blockers.append(f"{extra['cross_split_exact_duplicate_clusters']} exact-duplicate cluster(s) span train and holdout")
    pothole = sum("roads/pothole" in r.image_labels for r in ann_hold)
    precision_valid = bool(ann_hold) and 0 < pothole / len(ann_hold) < 0.99
    prov = build_provenance([r.model_dump() for r in ann_hold]) if ann_hold else None
    claims = claims_for("real_holdout", prov) if prov else None
    can_run = not blockers
    claim_blockers = list(claims["reasons"]) if claims else ["no holdout rows"]
    if not precision_valid and ann_hold:
        claim_blockers.append("holdout has (almost) only pothole images: precision is not meaningful without negatives")
    if card.license.status != "VERIFIED_PRIMARY":
        claim_blockers.append("licence not verified at the primary source")
    return {"annotated_holdout_images": len(ann_hold), "min_for_a_claim": MIN_REAL_N, "holdout_pothole_images": pothole, "pothole_precision_valid": precision_valid,
            "can_run_real_holdout": can_run, "run_blockers": blockers, "publishable_evaluation_enabled": False if claim_blockers else True,
            "claim_blockers": sorted(set(claim_blockers)), "claims_block": claims}


def run_image_dataset(cfg: RunConfig, dataset_id: str) -> dict:
    spec, card = SPECS[dataset_id], load_card(dataset_id)
    res = _new(card, spec)
    d = cfg.out / dataset_id
    _stage(res, "card_provenance", "ok", {"licence": f"{card.license.status}: {card.license.name}", "conflicts": card.license.conflicts, "identity": card.identity_status,
                                          "priority": card.priority, "restrictions": card.restrictions})
    loc = locate(spec, cfg.input_root, cfg.paths.get(dataset_id))
    res["location"] = loc.to_dict()
    if not loc.found:
        res["status"] = "NOT_ATTACHED"
        _stage(res, "locate", "blocked", loc.message)
        res["next_steps"].append(loc.message)
        return res
    root = loc.path
    assert root is not None
    _stage(res, "locate", "ok", {"path": str(root), "how": loc.how, "files": loc.structure["files"], "images": loc.structure["images"],
                                 "xml_annotation_files": loc.structure["xml_annotation_files"]})
    prof = profile_image_dataset(root)
    _write_json(d / "image_profile.json", prof)
    res["artifacts"].append(f"{dataset_id}/image_profile.json")
    _stage(res, "profile_images", "ok", {"n_images": prof["n_images"], "extensions": prof["extensions"], "annotation_artifacts": prof["annotation_artifacts"],
                                         "format_candidates_NOT_DECISIONS": prof["format_candidates"], "class_name_files": prof["class_name_files"], "coco_style_json": prof["coco_style_json"],
                                         "n_image_directories": prof["n_image_directories"], "largest_image_directories": prof["largest_image_directories"],
                                         "numbered_filename_share": prof["numbered_filename_share"], "sample_relative_paths": prof["sample_relative_paths"][:6], "warnings": prof["warnings"]})
    _stage(res, "video_frame_relationships", "ok", video_frame_relationships(prof))
    ic = _image_cfg(cfg, spec)
    fmt = ic["format"]
    cand = prof["format_candidates"]
    if not fmt:
        res["status"] = "NEEDS_CONFIG"
        _stage(res, "annotation_format", "blocked", f"annotation format not set. The profile suggests candidates {cand} but the notebook never guesses: set IMAGE['{dataset_id}']['format'] after looking at the samples.")
        res["next_steps"].append(f"Inspect image_profile.json (candidates {cand}, class-name files {prof['class_name_files']}), then set IMAGE['{dataset_id}'] = {{'format': 'voc'|'yolo'|'coco'|'folder', ...}}.")
        return res
    if spec.default_format and spec.default_format not in cand:
        res["status"] = "BLOCKED"
        _stage(res, "annotation_format", "blocked", f"{dataset_id} is documented as {spec.default_format.upper()} but the profile shows candidates {cand}: this attached copy does not look like the documented layout. Nothing was prepared.")
        res["next_steps"].append("Check that the attached copy contains the annotation files (…/annotations/xmls/*.xml), or override the path/format after inspecting the profile.")
        return res
    names_file = ic["class_names_file"]
    if fmt == "yolo":
        if not names_file:
            res["status"] = "NEEDS_CONFIG"
            _stage(res, "class_names", "blocked", f"YOLO labels hold numeric class ids; the dataset's own class-names file is required (never guessed). Candidates found: {prof['class_name_files']}")
            res["next_steps"].append(f"Set IMAGE['{dataset_id}']['class_names_file'] to the dataset's class list (found: {prof['class_name_files'] or 'none — obtain it from the dataset documentation'}).")
            return res
        names_file = str(Path(names_file) if Path(names_file).is_absolute() else root / names_file)
        try:
            _stage(res, "class_names", "ok", {"file": Path(names_file).name, "classes": load_class_names(Path(names_file))})
        except DataSourceError as e:
            res["status"] = "NEEDS_CONFIG"
            _stage(res, "class_names", "blocked", str(e))
            res["next_steps"].append(str(e))
            return res
    _stage(res, "annotation_format", "ok", {"format": fmt, "source": "operator setting" if cfg.image.get(dataset_id, {}).get("format") else f"the dataset's documented format ({spec.default_format}), confirmed by the profile"})
    if not _terms(res, card, cfg):
        return res
    # holdout only with an explicit group rule: otherwise prepare for profiling/mapping/audit but build NO split
    explicit_group = bool(cfg.image.get(dataset_id, {}).get("group_by")) or dataset_id in ("rdd2022", "rdd2020")
    frac = float(ic["holdout_fraction"] or 0.0)
    if frac and not explicit_group:
        frac = 0.0
        _stage(res, "holdout_rule", "warning", "holdout_fraction was set but no group_by rule: random frame splits leak near-identical frames, so NO holdout was generated.")
        res["next_steps"].append(f"Set IMAGE['{dataset_id}']['group_by'] ('dir' | 'regex' + group_regex | 'block') after reading the profile, then re-run to build a group-safe holdout.")
    try:
        if spec.needs_xml_annotations:
            man = prep.prepare_rdd(card, root, d / "prepared", default_country=ic["default_country"], holdout_fraction=frac, holdout_seed=int(ic["holdout_seed"]),
                                   block_size=int(ic["block_size"]), retrieved_at=cfg.retrieved_at)
            cov = man["box_mapping_coverage"]
            labels = man["boxes_per_class"]
        else:
            man = prep.prepare_images(card, root, d / "prepared", fmt=fmt, class_names_file=Path(names_file) if names_file else None, group_by=ic["group_by"] or "dir",
                                      group_regex=ic["group_regex"], block_size=int(ic["block_size"]), label_from=ic["label_from"], holdout_fraction=frac,
                                      holdout_seed=int(ic["holdout_seed"]), retrieved_at=cfg.retrieved_at)
            cov = man["box_or_label_mapping_coverage"]
            labels = man["source_label_counts"]
    except DataSourceError as e:
        res["status"] = "NEEDS_CONFIG"
        _stage(res, "prepare", "blocked", str(e))
        res["next_steps"].append(str(e))
        return res
    res["artifacts"].append(f"{dataset_id}/prepared/PREPARE_MANIFEST.json")
    _stage(res, "prepare", "ok", {"records": man["records"], "split_counts": man["split_counts"], "adapter_stats": man["adapter_stats"], "options": man["options"],
                                  "group_rule": ("index-block heuristic (RDD)" if spec.needs_xml_annotations else (ic["group_by"] or "dir (descriptive only, no holdout)"))})
    unm = [k for k in (cov.get("top_unmapped_source_labels") or [])]
    _stage(res, "mapping_validation", "warning" if unm else "ok", {"coverage_share": cov.get("share"), "source_labels_seen": labels, "top_unmapped": unm,
                                                                      "out_of_scope": cov.get("top_out_of_scope_source_labels"), "mapping_status": man["mapping"]["status"],
                                                                      "note": "labels are mapped by an explicit DRAFT table; anything unmapped is reported, never forced into the taxonomy"})
    recs = [ImageRecord.model_validate(r) for r in read_jsonl(d / "prepared" / "records.jsonl")]
    ann, grp = annotation_audit(recs), group_audit(recs)
    group_of, split_of = {r.image_relpath: r.group_id for r in recs}, {r.image_relpath: r.split_hint for r in recs}
    files = image_files_audit(root, [r.image_relpath for r in recs], group_of=group_of.get, split_of=split_of.get,
                              max_files=cfg.audit_max_files, max_near_dup_images=cfg.audit_max_near_dup_images)
    _write_json(d / "image_audit.json", {"annotations": ann, "groups": grp, "files": files})
    res["artifacts"].append(f"{dataset_id}/image_audit.json")
    _stage(res, "annotation_audit", "ok", ann)
    _stage(res, "group_audit", "ok", grp)
    _stage(res, "image_file_and_duplicate_audit", "ok" if files["near_duplicates"]["status"] == "ok" else "warning", files)
    extra = {"n_groups": grp["n_groups"], "straddling_groups": grp["groups_straddling_train_and_holdout"],
             "cross_split_near_duplicate_pairs": files["near_duplicates"].get("pairs_spanning_train_and_holdout", 0),
             "cross_split_exact_duplicate_clusters": files["exact_duplicates"].get("clusters_spanning_train_and_holdout", 0)}
    rd = _readiness(card, recs, extra)
    res["real_holdout_readiness"] = {k: v for k, v in rd.items() if k != "claims_block"}
    res["real_holdout_readiness"]["banner_if_run"] = rd["claims_block"]["banner"] if rd["claims_block"] else None
    _stage(res, "real_holdout_readiness", "ok" if rd["can_run_real_holdout"] else "warning", res["real_holdout_readiness"])
    if rd["run_blockers"]:
        res["next_steps"].extend(rd["run_blockers"])
    if rd["claim_blockers"]:
        res["next_steps"].append("No real-world claim can be made yet: " + "; ".join(rd["claim_blockers"]))
    if cfg.run_provider_eval and rd["can_run_real_holdout"]:
        from ai.evaluation import run_eval
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = run_eval.main(["--task", "vision", "--track", "real_holdout", "--real-data", str(d / "prepared" / "records.jsonl"), "--image-root", str(root),
                                "--out", str(d / "results"), "--name", f"{dataset_id}_vision_real_holdout", "--system", "provider"])
        _stage(res, "provider_vision_evaluation", "ok" if rc == 0 else "skipped",
               {"exit_code": rc, "report": f"{dataset_id}/results/{dataset_id}_vision_real_holdout.json" if rc == 0 else None,
                "note": None if rc == 0 else buf.getvalue().strip()[-300:]})
    else:
        _stage(res, "provider_vision_evaluation", "not_requested", "no model/provider call was made (run_provider_eval is off by default; the first run only establishes what is inside the dataset)"
               if not cfg.run_provider_eval else "skipped: real_holdout is not runnable yet (see readiness blockers)")
    return res


RUNNERS = {"bmc_mumbai": run_bmc, **{i: (lambda cfg, i=i: run_image_dataset(cfg, i)) for i in IMAGE_IDS}}


# ------------------------------------------------------------------------------------------------ orchestration + reports
def plan(cfg: RunConfig, ids: tuple[str, ...] = ORDER) -> list[dict]:
    """What is attached / missing for each dataset (no processing)."""
    out, seen = [], {}
    for i in ids:
        loc: Location = locate(SPECS[i], cfg.input_root, cfg.paths.get(i))
        row = {**loc.to_dict(), "title": SPECS[i].title, "priority": load_card(i).priority, "licence_status": load_card(i).license.status}
        if loc.found and loc.path is not None:
            if loc.path in seen:
                row["ambiguity"] = f"the same mount is claimed by {seen[loc.path]} and {i}: set an explicit path for one of them"
            seen[loc.path] = i
        out.append(row)
    return out


def render_md(res: dict) -> str:
    c = res["card"]
    L = [f"# {res['title']} — `{res['dataset_id']}`", "", f"**Status: {res['status']}** · evidence class: `{res['evidence_class']}` · real-world claim allowed: **{res['real_world_claim_allowed']}**", "",
         f"- priority: {c['priority']} · licence: **{c['licence_status']}** ({c['licence_name']}) · origin: {c['origin_status']} · identity: {c['identity_status']}"]
    if c["licence_conflicts"]:
        L.append(f"- licence CONFLICT: {'; '.join(c['licence_conflicts'])}")
    L += ["", "| stage | status | detail (truncated) |", "|---|---|---|"]
    for s in res["stages"]:
        det = json.dumps(s["detail"], ensure_ascii=False, default=str) if not isinstance(s["detail"], str) else s["detail"]
        L.append(f"| {s['stage']} | {s['status']} | {det[:220].replace('|', '/')}{'…' if len(det) > 220 else ''} |")
    if res.get("real_holdout_readiness"):
        r = res["real_holdout_readiness"]
        L += ["", "## real_holdout readiness", f"- can run a real_holdout evaluation: **{r['can_run_real_holdout']}**", f"- publishable / claimable: **{r['publishable_evaluation_enabled']}**"]
        L += [f"- run blocker: {b}" for b in r["run_blockers"]] + [f"- claim blocker: {b}" for b in r["claim_blockers"]]
    if res["next_steps"]:
        L += ["", "## What to do next"] + [f"- {n}" for n in res["next_steps"]]
    return "\n".join(L) + "\n"


def run_dataset(cfg: RunConfig, dataset_id: str) -> dict:
    try:
        res = _finalize(RUNNERS[dataset_id](cfg))
    except Exception as e:   # noqa: BLE001  (one dataset must never stop the others; the failure is reported verbatim)
        card = load_card(dataset_id)
        res = _new(card, SPECS[dataset_id])
        res["status"] = "FAILED"
        _stage(res, "unexpected_error", "failed", f"{type(e).__name__}: {e}")
        res["next_steps"].append("Unexpected error: please report it with this message. No partial result should be trusted.")
    d = cfg.out / dataset_id
    _write_json(d / "report.json", res)
    (d / "report.md").write_text(render_md(res), encoding="utf-8")
    return res


def run_all(cfg: RunConfig, ids: tuple[str, ...] = ORDER) -> dict:
    unknown = [i for i in ids if i not in SPECS]
    if unknown:
        raise DataSourceError(f"unknown dataset ids {unknown}; known: {sorted(SPECS)}")
    results = {i: run_dataset(cfg, i) for i in ids}
    summary = {"created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "input_root": str(input_root(cfg.input_root)), "attached_inputs": describe_inputs(cfg.input_root),
               "datasets": {i: {"status": r["status"], "priority": r["card"]["priority"], "evidence_class": r["evidence_class"], "licence_status": r["card"]["licence_status"],
                                "real_world_claim_allowed": r["real_world_claim_allowed"], "next_steps": r["next_steps"],
                                "can_run_real_holdout": (r.get("real_holdout_readiness") or {}).get("can_run_real_holdout")} for i, r in results.items()},
               "reminder": "BMC is third-party SYNTHETIC data (never real-world evidence); image datasets are real but every licence is UNVERIFIED here: no publishable claim."}
    _write_json(cfg.out / "SUMMARY.json", summary)
    L = ["# CivicConnect Kaggle real-data run — summary", "", "| dataset | priority | status | evidence | licence | can run real_holdout |", "|---|---|---|---|---|---|"]
    for i, v in summary["datasets"].items():
        L.append(f"| `{i}` | {v['priority']} | **{v['status']}** | {v['evidence_class']} | {v['licence_status']} | {v['can_run_real_holdout']} |")
    L += ["", summary["reminder"], ""]
    for i, v in summary["datasets"].items():
        if v["next_steps"]:
            L += [f"## {i}"] + [f"- {n}" for n in v["next_steps"]] + [""]
    (cfg.out / "SUMMARY.md").write_text("\n".join(L), encoding="utf-8")
    return summary


def bundle(cfg: RunConfig) -> Path:
    """Zip of reports/manifests/profiles only: prepared records, raw data and images are never included."""
    out = cfg.out
    z_path = Path(cfg.work_dir) / "civic_real_aggregates.zip"
    with zipfile.ZipFile(z_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.rglob("*")):
            if p.is_file() and p.suffix in (".json", ".md") and not p.name.endswith(NEVER_BUNDLED):
                z.write(p, p.relative_to(out).as_posix())
        assert not any(n.endswith(NEVER_BUNDLED + (".jpg", ".jpeg", ".png", ".csv")) for n in z.namelist())
    return z_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--datasets", nargs="*", default=list(ORDER), choices=sorted(SPECS))
    ap.add_argument("--input-root", type=Path, default=None, help="default: $CIVIC_KAGGLE_INPUT or /kaggle/input")
    ap.add_argument("--work-dir", type=Path, default=Path("/kaggle/working"))
    ap.add_argument("--accept-terms", nargs="*", default=[])
    ap.add_argument("--acknowledge-unverified-license", action="store_true")
    ap.add_argument("--plan-only", action="store_true", help="only report what is attached / missing")
    ap.add_argument("--config", type=Path, help="JSON file with RunConfig fields (paths, files, role_map, image, ...)")
    a = ap.parse_args(argv)
    fields = json.loads(a.config.read_text(encoding="utf-8")) if a.config else {}
    cfg = RunConfig(work_dir=a.work_dir, input_root=a.input_root, accept_terms=a.accept_terms, ack_unverified_license=a.acknowledge_unverified_license, **fields)
    if a.plan_only:
        print(json.dumps(plan(cfg, tuple(a.datasets)), indent=2))
        return 0
    s = run_all(cfg, tuple(a.datasets))
    print(json.dumps({k: v["status"] for k, v in s["datasets"].items()}, indent=2))
    print("aggregates:", bundle(cfg))
    return 0 if all(v["status"] != "FAILED" for v in s["datasets"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
