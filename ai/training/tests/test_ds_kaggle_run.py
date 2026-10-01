"""Kaggle-in-place orchestration, dataset by dataset, on an INVENTED /kaggle/input-shaped tree (nothing real, nothing downloaded)."""
import json
import zipfile

import pytest

from ai.training.src.data_sources import kaggle_run as kr
from ai.training.src.data_sources.errors import DataSourceError

pytest.importorskip("PIL", reason="Pillow builds the test images")

from .conftest_real import make_fake_kaggle_input, make_real_jpeg, write_voc  # noqa: E402

ALL_TERMS = ["bmc_mumbai", "rdd2022", "rdd2020", "bharatpothole", "mumbai_nashik_road_surface"]
SECRETS = ("INVENTED PERSON", "INVENTED CONTRACTOR", "SENTINEL-", "Resolved:")


def cfg_for(tmp_path, root, **kw):
    base = dict(work_dir=tmp_path / "work", input_root=root, accept_terms=ALL_TERMS, ack_unverified_license=True)
    base.update(kw)
    return kr.RunConfig(**base)


def stage(res, name):
    return next(s for s in res["stages"] if s["stage"] == name)


def report(cfg, ds):
    return json.loads((cfg.out / ds / "report.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ nothing attached
def test_empty_input_reports_exactly_what_is_missing_for_every_dataset(tmp_path):
    root = tmp_path / "in"
    root.mkdir()
    cfg = cfg_for(tmp_path, root)
    s = kr.run_all(cfg)
    assert {v["status"] for v in s["datasets"].values()} == {"NOT_ATTACHED"}
    for ds, v in s["datasets"].items():
        msg = " ".join(v["next_steps"])
        assert "NOT FOUND" in msg and "HOW TO ATTACH" in msg and "EXPECTED LAYOUT" in msg, ds
    assert (cfg.out / "SUMMARY.md").is_file() and not list(cfg.out.rglob("records.jsonl"))


def test_plan_is_read_only_and_flags_a_mount_claimed_by_two_datasets(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", rdd2022=False)
    both = root / "rdd2020-and-rdd2022"
    write_voc(both, "India", "train", "India_1", [("D40", 1, 1, 9, 9)])
    make_real_jpeg(both / "India" / "train" / "images" / "India_1.jpg", 1)
    plan = {p["dataset_id"]: p for p in kr.plan(cfg_for(tmp_path, root))}
    assert plan["rdd2022"]["found"] and plan["rdd2020"]["found"] and "ambiguity" in plan["rdd2020"]
    assert not plan["bharatpothole"]["found"] and plan["bmc_mumbai"]["found"]
    assert not (tmp_path / "work").exists()                           # planning writes nothing


# ------------------------------------------------------------------ BMC: third-party SYNTHETIC dataset
def test_bmc_runs_profile_policy_leakage_and_synthetic_evaluation(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", rdd2022=False)
    cfg = cfg_for(tmp_path, root)
    res = kr.run_dataset(cfg, "bmc_mumbai")
    assert res["status"] == "OK" and res["evidence_class"] == "third_party_synthetic" and res["real_world_claim_allowed"] is False
    names = [s["stage"] for s in res["stages"]]
    assert names == ["card_provenance", "locate", "select_data_file", "profile_and_role_validation", "mapping_validation", "determinism_preflight", "terms_gate",
                     "prepare", "leakage_audit", "synthetic_evaluation"]
    roles = stage(res, "profile_and_role_validation")["detail"]
    assert roles["unclassified_columns_default_denied"] == ["UNCLASSIFIED_SENTINEL_COL"] and "complaint_date" in roles["resolved_roles"].values()
    assert set(roles["pii_columns_never_read"]) == {"complainant_name", "contractor_name"} and not roles["missing_required_roles"]
    prep = stage(res, "prepare")["detail"]
    assert prep["source_kind"] == "synthetic_third_party" and prep["holdout_rule"].startswith("time") and prep["split_counts"]["holdout"] > 0
    leak = stage(res, "leakage_audit")["detail"]["tasks"]
    assert leak["routing_agreement"]["audit_passed"] is False and leak["resolution_time_prior"]["audit_passed"] is True
    ev = stage(res, "synthetic_evaluation")["detail"]
    assert ev["taxonomy_coverage"]["track"] == "descriptive"
    for t in ("resolution_time_prior", "recurrence_hotspot", "routing_agreement", "triage_priority_prior"):
        assert ev[t]["track"] == "synthetic" and ev[t]["real_world_claim_allowed"] is False and "THIRD-PARTY SYNTHETIC" in ev[t]["banner"], t
    assert ev["routing_agreement"]["meaningful"] is False and ev["resolution_time_prior"]["meaningful"] is True
    assert any("vacuous" in n for n in res["next_steps"]) and any("SYNTHETIC third-party" in n for n in res["next_steps"])
    assert (cfg.out / "bmc_mumbai" / "report.md").is_file() and (cfg.out / "bmc_mumbai" / "profile.json").is_file()


def test_bmc_never_leaks_pii_sensitive_or_post_resolution_text_into_any_report(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", rdd2022=False)
    cfg = cfg_for(tmp_path, root)
    kr.run_dataset(cfg, "bmc_mumbai")
    for p in cfg.out.rglob("*"):
        if p.is_file():
            text = p.read_text(encoding="utf-8")
            assert not any(s in text for s in SECRETS), p.name


def test_bmc_requires_terms_and_licence_acknowledgement_before_preparing(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", rdd2022=False)
    r = kr.run_dataset(cfg_for(tmp_path, root, accept_terms=[]), "bmc_mumbai")
    assert r["status"] == "NEEDS_TERMS" and "--accept-terms bmc_mumbai" in stage(r, "terms_gate")["detail"] and "SYNTHETIC DATA" in r["terms_summary"]
    assert not list((tmp_path / "work").rglob("records.jsonl"))
    r2 = kr.run_dataset(cfg_for(tmp_path, root, ack_unverified_license=False), "bmc_mumbai")
    assert r2["status"] == "NEEDS_TERMS" and "ACK_UNVERIFIED_LICENSE" in " ".join(r2["next_steps"])
    assert stage(r2, "profile_and_role_validation")["status"] == "ok"        # profiling needs no terms: it only reads in place


def test_bmc_ambiguous_columns_need_a_role_map_and_a_role_map_resolves_them(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", rdd2022=False)
    f = next(root.rglob("bmc_train.csv"))
    lines = f.read_text(encoding="utf-8").splitlines()
    f.write_text("\n".join([lines[0] + ",registered_date"] + [ln + ",2020-01-01" for ln in lines[1:]]) + "\n", encoding="utf-8")
    r = kr.run_dataset(cfg_for(tmp_path, root), "bmc_mumbai")
    assert r["status"] == "NEEDS_CONFIG" and "ambiguous" in stage(r, "profile_and_role_validation")["detail"]
    assert "--role-map" in r["next_steps"][0] and not list((tmp_path / "work").rglob("records.jsonl"))
    ok = kr.run_dataset(cfg_for(tmp_path, root, role_map={"complaint_date": "created_at"}), "bmc_mumbai")
    assert ok["status"] == "OK"
    detail = stage(ok, "profile_and_role_validation")["detail"]
    assert detail["resolved_roles"]["created_at"] == "complaint_date" and "registered_date" in detail["unclassified_columns_default_denied"]     # the loser is NOT used


def test_bmc_missing_required_roles_are_listed_with_the_real_headers(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", rdd2022=False)
    f = next(root.rglob("bmc_train.csv"))
    f.write_text("foo,bar\n1,2\n", encoding="utf-8")
    r = kr.run_dataset(cfg_for(tmp_path, root), "bmc_mumbai")
    assert r["status"] == "NEEDS_CONFIG"
    st = stage(r, "profile_and_role_validation")
    assert st["status"] == "blocked" and "source_category" in st["detail"]["missing_required_roles"]
    assert "['foo', 'bar']" in " ".join(r["next_steps"]) and "ROLE_MAP" in " ".join(r["next_steps"])


def test_bmc_with_two_candidate_training_files_asks_instead_of_choosing(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", rdd2022=False)
    comp = next(root.rglob("bmc_train.csv")).parent
    (comp / "bmc_train_extra.csv").write_text("a\n1\n", encoding="utf-8")
    r = kr.run_dataset(cfg_for(tmp_path, root), "bmc_mumbai")
    assert r["status"] == "NEEDS_CONFIG" and "FILES['bmc_mumbai']" in r["next_steps"][0]
    chosen = kr.run_dataset(cfg_for(tmp_path, root, files={"bmc_mumbai": str(comp / "bmc_train.csv")}), "bmc_mumbai")
    assert chosen["status"] == "OK"


def test_bmc_sampling_and_auto_holdout_are_deterministic(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", rdd2022=False)
    a = kr.run_dataset(cfg_for(tmp_path / "a", root, bmc_max_rows=60, bmc_sample_seed=3), "bmc_mumbai")
    b = kr.run_dataset(cfg_for(tmp_path / "b", root, bmc_max_rows=60, bmc_sample_seed=3), "bmc_mumbai")
    assert stage(a, "prepare")["detail"]["records"] == 60 == stage(b, "prepare")["detail"]["records"]
    assert stage(a, "prepare")["detail"]["split_counts"] == stage(b, "prepare")["detail"]["split_counts"]
    assert kr._auto_holdout_date(["2024-01-01T00:00:00", "2024-01-11T00:00:00"]) == "2024-01-09" and kr._auto_holdout_date(None) is None


def test_bmc_run_makes_no_provider_calls_and_needs_no_credentials(tmp_path, monkeypatch):
    for k in ("OPENAI_API_KEY", "AI_INTAKE_MODEL", "AI_EMBEDDING_MODEL"):
        monkeypatch.delenv(k, raising=False)
    import ai.evaluation.run_eval as re_
    monkeypatch.setattr(re_, "build_intake_system", lambda *a, **k: (_ for _ in ()).throw(AssertionError("a provider/classifier must not be built for BMC tasks")))
    root = make_fake_kaggle_input(tmp_path / "in", rdd2022=False)
    assert kr.run_dataset(cfg_for(tmp_path, root), "bmc_mumbai")["status"] == "OK"


# ------------------------------------------------------------------ RDD (VOC documented) — India
def test_rdd2022_profiles_validates_prepares_a_block_group_holdout_and_audits(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", bmc=False)
    cfg = cfg_for(tmp_path, root, image={"rdd2022": {"block_size": 5, "holdout_fraction": 0.5, "holdout_seed": 1}})
    res = kr.run_dataset(cfg, "rdd2022")
    assert res["status"] == "OK" and res["evidence_class"] == "real_public"
    names = [s["stage"] for s in res["stages"]]
    assert names[:5] == ["card_provenance", "locate", "profile_images", "video_frame_relationships", "annotation_format"]
    assert stage(res, "annotation_format")["detail"]["source"].startswith("the dataset's documented format")
    prep = stage(res, "prepare")["detail"]
    assert prep["split_counts"]["holdout"] > 0 and prep["split_counts"]["train"] > 0
    assert stage(res, "group_audit")["detail"]["groups_straddling_train_and_holdout"] == 0
    assert stage(res, "annotation_audit")["detail"]["source_class_counts"] == {"D40": 20, "D00": 20}
    assert stage(res, "mapping_validation")["detail"]["mapping_status"].startswith("DRAFT")
    files = stage(res, "image_file_and_duplicate_audit")["detail"]
    assert files["formats_by_magic_bytes"] == {"jpeg": 40} and files["near_duplicates"]["status"] == "ok"
    rd = res["real_holdout_readiness"]
    assert rd["annotated_holdout_images"] > 0 and rd["publishable_evaluation_enabled"] is False
    cb = " ".join(rd["claim_blockers"])
    assert "licence not verified" in cb and "< 200" in cb          # licence unresolved (BY vs BY-SA) AND too few rows
    assert stage(res, "provider_vision_evaluation")["status"] == "not_requested"
    assert any("licence" in c.lower() for c in res["card"]["licence_conflicts"])


def test_rdd_copy_whose_mount_is_the_india_folder_uses_default_country(tmp_path):
    root = tmp_path / "in"
    india = root / "rdd2022-india-only"
    for i in range(6):
        write_voc(india, "", "train", f"Img_{i:06d}", [("D40", 1, 1, 30, 30)], with_image=False)
        make_real_jpeg(india / "train" / "images" / f"Img_{i:06d}.jpg", i + 1)
    cfg = cfg_for(tmp_path, root)
    res = kr.run_dataset(cfg, "rdd2022")
    assert res["status"] == "OK"
    recs = [json.loads(ln) for ln in (cfg.out / "rdd2022" / "prepared" / "records.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {r["country"] for r in recs} == {"India"} and stage(res, "prepare")["detail"]["options"]["default_country"] == "India"


def test_rdd2020_is_a_separate_run_with_its_own_card_and_ids(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", bmc=False, rdd2022=False, rdd2020=True)
    cfg = cfg_for(tmp_path, root)
    res = kr.run_dataset(cfg, "rdd2020")
    assert res["status"] == "OK" and "NonCommercial" in res["card"]["licence_name"]
    ids = [json.loads(ln)["record_id"] for ln in (cfg.out / "rdd2020" / "prepared" / "records.jsonl").read_text(encoding="utf-8").splitlines()]
    assert all(i.startswith("rdd2020:") for i in ids)
    assert kr.run_dataset(cfg, "rdd2022")["status"] == "NOT_ATTACHED"


def test_a_name_match_without_voc_annotations_is_not_used_for_rdd(tmp_path):
    root = tmp_path / "in" / "rdd2022-india"
    for i in range(3):
        make_real_jpeg(root / "images" / f"x{i}.jpg", i)
    res = kr.run_dataset(cfg_for(tmp_path, tmp_path / "in"), "rdd2022")
    assert res["status"] == "NOT_ATTACHED" and "NOT USABLE" in res["next_steps"][0] and "annotations" in res["next_steps"][0]
    assert not list((tmp_path / "work").rglob("records.jsonl"))


# ------------------------------------------------------------------ BharatPotHole: nothing assumed
def test_bharatpothole_stops_at_profile_until_format_and_class_names_are_given(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", bmc=False, rdd2022=False, bharat=True)
    cfg = cfg_for(tmp_path, root)
    r1 = kr.run_dataset(cfg, "bharatpothole")
    assert r1["status"] == "NEEDS_CONFIG" and stage(r1, "profile_images")["detail"]["n_images"] == 30
    assert "yolo" in stage(r1, "profile_images")["detail"]["format_candidates_NOT_DECISIONS"] and "never guesses" in stage(r1, "annotation_format")["detail"]
    assert not list(cfg.out.rglob("records.jsonl"))
    r2 = kr.run_dataset(cfg_for(tmp_path, root, image={"bharatpothole": {"format": "yolo"}}), "bharatpothole")
    assert r2["status"] == "NEEDS_CONFIG" and "class-names file is required" in stage(r2, "class_names")["detail"] and "classes.txt" in stage(r2, "class_names")["detail"]
    r3 = kr.run_dataset(cfg_for(tmp_path, root, image={"bharatpothole": {"format": "yolo", "class_names_file": "classes.txt"}}), "bharatpothole")
    assert r3["status"] == "OK" and stage(r3, "class_names")["detail"]["classes"] == ["pothole"]
    assert not any(x["stage"] == "holdout_rule" for x in r3["stages"]) and stage(r3, "prepare")["detail"]["split_counts"] == {"none": 30}


def test_bharatpothole_holdout_needs_an_explicit_group_rule_and_keeps_videos_whole(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", bmc=False, rdd2022=False, bharat=True)
    base = {"format": "yolo", "class_names_file": "classes.txt", "holdout_fraction": 0.5}
    none = kr.run_dataset(cfg_for(tmp_path / "a", root, image={"bharatpothole": base}), "bharatpothole")
    assert stage(none, "holdout_rule")["status"] == "warning" and stage(none, "prepare")["detail"]["split_counts"] == {"none": 30}
    assert none["real_holdout_readiness"]["can_run_real_holdout"] is False
    ruled = kr.run_dataset(cfg_for(tmp_path / "b", root, image={"bharatpothole": {**base, "group_by": "regex", "group_regex": r"^(vid\d+)_", "holdout_seed": 2}}), "bharatpothole")
    assert ruled["status"] == "OK" and stage(ruled, "group_audit")["detail"]["groups_straddling_train_and_holdout"] == 0
    assert stage(ruled, "group_audit")["detail"]["n_groups"] == 6


def test_positive_only_and_small_holdouts_block_claims_and_licence_unknown_disables_publishing(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", bmc=False, rdd2022=False, bharat=True)
    cfg = cfg_for(tmp_path, root, image={"bharatpothole": {"format": "yolo", "class_names_file": "classes.txt", "holdout_fraction": 0.5, "group_by": "regex",
                                                          "group_regex": r"^(vid\d+)_", "holdout_seed": 2}})
    rd = kr.run_dataset(cfg, "bharatpothole")["real_holdout_readiness"]
    text = " ".join(rd["claim_blockers"])
    assert rd["publishable_evaluation_enabled"] is False and rd["pothole_precision_valid"] is False
    assert "only pothole images" in text and "licence not verified" in text and "< 200" in text


def test_cross_split_duplicate_frames_block_the_real_holdout(tmp_path):
    root = tmp_path / "in" / "bharatpothole"
    for v in range(8):
        for f in range(3):
            make_real_jpeg(root / "images" / f"vid{v}_f{f}.jpg", 5)                       # every frame is the SAME picture: perfect leakage
            (root / "labels").mkdir(exist_ok=True)
            (root / "labels" / f"vid{v}_f{f}.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    (root / "classes.txt").write_text("pothole\n", encoding="utf-8")
    cfg = cfg_for(tmp_path, tmp_path / "in", image={"bharatpothole": {"format": "yolo", "class_names_file": "classes.txt", "holdout_fraction": 0.5, "group_by": "regex",
                                                                     "group_regex": r"^(vid\d+)_", "holdout_seed": 1}})
    res = kr.run_dataset(cfg, "bharatpothole")
    rd = res["real_holdout_readiness"]
    assert rd["can_run_real_holdout"] is False
    assert any("near-duplicate" in b for b in rd["run_blockers"]) and any("exact-duplicate" in b for b in rd["run_blockers"])
    assert stage(res, "image_file_and_duplicate_audit")["detail"]["exact_duplicates"]["clusters_spanning_train_and_holdout"] >= 1


def test_terms_gate_blocks_image_preparation_until_accepted(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", bmc=False, rdd2022=False, bharat=True)
    r = kr.run_dataset(cfg_for(tmp_path, root, accept_terms=[], image={"bharatpothole": {"format": "yolo", "class_names_file": "classes.txt"}}), "bharatpothole")
    assert r["status"] == "NEEDS_TERMS" and "bharatpothole" in " ".join(r["next_steps"])
    assert "NOT STATED" in r["terms_summary"]
    assert not list((tmp_path / "work").rglob("records.jsonl"))


# ------------------------------------------------------------------ Mumbai/Nashik: folder labels only as far as the labels go
def test_mumbai_nashik_needs_an_explicit_format_then_maps_only_what_the_labels_support(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", bmc=False, rdd2022=False, nashik=True)
    r1 = kr.run_dataset(cfg_for(tmp_path / "a", root), "mumbai_nashik_road_surface")
    assert r1["status"] == "NEEDS_CONFIG" and "folder" in json.dumps(stage(r1, "profile_images")["detail"]["format_candidates_NOT_DECISIONS"])
    cfg = cfg_for(tmp_path / "b", root, image={"mumbai_nashik_road_surface": {"format": "folder", "group_by": "dir", "holdout_fraction": 0.5, "holdout_seed": 4}})
    r2 = kr.run_dataset(cfg, "mumbai_nashik_road_surface")
    assert r2["status"] == "OK" and r2["card"]["identity_status"] == "CONFIRMED_BY_USER" and r2["card"]["licence_verified"] is False
    ann = stage(r2, "annotation_audit")["detail"]
    assert ann["image_level_mapped_label_counts"].get("roads/pothole") == 4
    assert set(ann["image_level_mapped_label_counts"]) <= {"roads/pothole", "(none mapped)"}          # paved/unpaved/speed breaker are NOT forced into the taxonomy
    assert stage(r2, "mapping_validation")["detail"]["out_of_scope"]
    assert r2["real_holdout_readiness"]["publishable_evaluation_enabled"] is False


# ------------------------------------------------------------------ provider evaluation is opt-in and never blocks profiling
def test_provider_eval_is_skipped_not_failed_when_requested_without_credentials(tmp_path, monkeypatch):
    for k in ("OPENAI_API_KEY", "AI_INTAKE_MODEL"):
        monkeypatch.delenv(k, raising=False)
    root = make_fake_kaggle_input(tmp_path / "in", bmc=False, rdd2022=False, bharat=True)
    cfg = cfg_for(tmp_path, root, run_provider_eval=True, image={"bharatpothole": {"format": "yolo", "class_names_file": "classes.txt", "holdout_fraction": 0.5, "group_by": "regex",
                                                                                  "group_regex": r"^(vid\d+)_", "holdout_seed": 2}})
    res = kr.run_dataset(cfg, "bharatpothole")
    ev = stage(res, "provider_vision_evaluation")
    assert res["status"] in ("OK", "PARTIAL") and ev["status"] in ("skipped", "not_requested")
    assert not list(cfg.out.rglob("*vision_real_holdout.json"))


# ------------------------------------------------------------------ orchestration, bundle, CLI
def test_datasets_run_independently_and_the_bundle_contains_aggregates_only(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", bharat=True)
    cfg = cfg_for(tmp_path, root, image={"rdd2022": {"block_size": 5, "holdout_fraction": 0.5}, "bharatpothole": {"format": "yolo", "class_names_file": "classes.txt"}})
    s = kr.run_all(cfg)
    st = {k: v["status"] for k, v in s["datasets"].items()}
    assert st["bmc_mumbai"] == "OK" and st["rdd2022"] == "OK" and st["bharatpothole"] == "OK"
    assert st["rdd2020"] == "NOT_ATTACHED" and st["mumbai_nashik_road_surface"] == "NOT_ATTACHED"
    assert s["datasets"]["bmc_mumbai"]["evidence_class"] == "third_party_synthetic" and s["datasets"]["rdd2022"]["evidence_class"] == "real_public"
    assert all(v["real_world_claim_allowed"] is False for v in s["datasets"].values())
    z = kr.bundle(cfg)
    names = zipfile.ZipFile(z).namelist()
    assert "SUMMARY.md" in names and any(n.endswith("bmc_mumbai/report.md") for n in names)
    assert not any(n.endswith(("records.jsonl", ".jpg", ".csv")) for n in names)
    assert any(cfg.out.rglob("records.jsonl"))                              # records exist in the work dir but are excluded from the bundle


def test_a_crash_in_one_dataset_is_reported_and_does_not_stop_the_others(tmp_path, monkeypatch):
    root = make_fake_kaggle_input(tmp_path / "in")
    monkeypatch.setitem(kr.RUNNERS, "bmc_mumbai", lambda cfg: (_ for _ in ()).throw(RuntimeError("boom")))
    s = kr.run_all(cfg_for(tmp_path, root, image={"rdd2022": {"block_size": 5, "holdout_fraction": 0.5}}), ("bmc_mumbai", "rdd2022"))
    assert s["datasets"]["bmc_mumbai"]["status"] == "FAILED" and s["datasets"]["rdd2022"]["status"] == "OK"
    assert "RuntimeError: boom" in json.dumps(json.loads((tmp_path / "work" / "civic_real" / "bmc_mumbai" / "report.json").read_text(encoding="utf-8")))


def test_unknown_dataset_ids_and_unsafe_work_dirs_are_refused(tmp_path):
    with pytest.raises(DataSourceError, match="unknown dataset"):
        kr.run_all(cfg_for(tmp_path, tmp_path), ("nope",))
    from ai.training.src.data_sources.errors import UnsafeOutputPath
    from ai.training.src.data_sources.paths import REPO_ROOT
    with pytest.raises(UnsafeOutputPath):
        _ = kr.RunConfig(work_dir=REPO_ROOT / "ai" / "evaluation").out


def test_cli_plan_only_and_run(tmp_path, capsys):
    root = make_fake_kaggle_input(tmp_path / "in")
    assert kr.main(["--input-root", str(root), "--plan-only"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert {p["dataset_id"]: p["found"] for p in plan}["bmc_mumbai"] is True
    cfgf = tmp_path / "cfg.json"
    cfgf.write_text(json.dumps({"image": {"rdd2022": {"block_size": 5, "holdout_fraction": 0.5}}}), encoding="utf-8")
    rc = kr.main(["--input-root", str(root), "--work-dir", str(tmp_path / "w"), "--datasets", "bmc_mumbai", "rdd2022", "--accept-terms", "bmc_mumbai", "rdd2022",
                  "--acknowledge-unverified-license", "--config", str(cfgf)])
    assert rc == 0 and (tmp_path / "w" / "civic_real_aggregates.zip").is_file()
