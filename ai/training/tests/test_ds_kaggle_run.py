"""Kaggle-in-place orchestration, dataset by dataset, on an INVENTED /kaggle/input-shaped tree (nothing real, nothing downloaded)."""
import json
import zipfile

import pytest

from ai.training.src.data_sources import kaggle_run as kr
from ai.training.src.data_sources.errors import DataSourceError

pytest.importorskip("PIL", reason="Pillow builds the test images")

from .conftest_real import make_fake_kaggle_input, make_rdd_copy, make_real_jpeg, write_voc  # noqa: E402

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
    assert names == ["card_provenance", "locate", "select_data_file", "data_dictionary", "profile_and_role_validation", "mapping_validation", "determinism_preflight",
                     "terms_gate", "prepare", "leakage_audit", "synthetic_evaluation"]
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


# ------------------------------------------------------------------ RDD2022 (exact Kaggle copy aliabdelmenam/rdd-2022): nothing assumed about its layout
RDD_FIRST_PASS = {}
VOC_CFG = {"rdd2022": {"format": "voc", "group_by": "block", "block_size": 5, "holdout_fraction": 0.5, "holdout_seed": 1}}


def test_rdd2022_first_pass_profiles_the_real_tree_and_stops_for_explicit_configuration(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", bmc=False, rdd2022_layout="yolo_split")
    cfg = cfg_for(tmp_path, root)
    res = kr.run_dataset(cfg, "rdd2022")
    assert res["status"] == "NEEDS_CONFIG" and res["evidence_class"] == "real_public"
    prof = stage(res, "profile_images")["detail"]
    assert prof["format_candidates"] == ["yolo", "folder"] and prof["split_directories_images"] == {"train": 30, "val": 5, "test": 5}
    assert prof["class_name_files"] == ["data.yaml"] and prof["class_name_previews"][0]["names_first_30"] == ["D00", "D10", "D20", "D40"]
    assert prof["suggested_config_NOT_APPLIED"] == {"format": "yolo", "class_names_file": "data.yaml"}
    assert any(o["dir"] == "train/images" for o in prof["directory_outline"]) and prof["images_with_same_stem_annotation"] == 40
    assert any("split-like directories" in w for w in prof["warnings"])
    assert "never guesses" in stage(res, "annotation_format")["detail"] and "IMAGE['rdd2022'] = " in res["next_steps"][0] and "'format': 'yolo'" in res["next_steps"][0]
    assert not list(cfg.out.rglob("records.jsonl"))                                            # nothing was prepared on a guess


def test_rdd2022_yolo_copy_prepares_with_its_own_class_file_and_source_splits_only_when_opted_in(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", bmc=False, rdd2022_layout="yolo_split")
    base = {"format": "yolo", "class_names_file": "data.yaml"}
    plain = kr.run_dataset(cfg_for(tmp_path / "a", root, image={"rdd2022": base}), "rdd2022")
    assert plain["status"] == "OK" and stage(plain, "prepare")["detail"]["split_counts"] == {"none": 40}          # source splits are NOT used by default
    assert stage(plain, "annotation_audit")["detail"]["source_class_counts"] == {"D00": 10, "D10": 10, "D20": 10, "D40": 10}
    assert stage(plain, "mapping_validation")["detail"]["mapping_status"].startswith("DRAFT")
    src = kr.run_dataset(cfg_for(tmp_path / "b", root, image={"rdd2022": {**base, "split_from_path": True}}), "rdd2022")
    sc = stage(src, "prepare")["detail"]["split_counts"]
    assert sc == {"train": 30, "holdout": 10} and src["real_holdout_readiness"]["annotated_holdout_images"] == 10
    both = kr.run_dataset(cfg_for(tmp_path / "c", root, image={"rdd2022": {**base, "split_from_path": True, "group_by": "block", "holdout_fraction": 0.3}}), "rdd2022")
    assert both["status"] == "NEEDS_CONFIG" and "choose one" in stage(both, "holdout_rule")["detail"]


def test_rdd2022_class_names_instead_of_codes_still_map_without_inventing_categories(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", bmc=False, rdd2022_layout="yolo_named")
    res = kr.run_dataset(cfg_for(tmp_path, root, image={"rdd2022": {"format": "yolo", "class_names_file": "data.yaml"}}), "rdd2022")
    ann = stage(res, "annotation_audit")["detail"]
    assert res["status"] == "OK" and set(ann["source_class_counts"]) == {"pothole", "longitudinal crack", "transverse crack", "alligator crack"}
    assert set(ann["mapped_box_label_counts"]) == {"roads/pothole", "roads"}                  # cracks stay category-level: no new taxonomy category
    assert not stage(res, "mapping_validation")["detail"]["top_unmapped"]


def test_rdd2022_voc_copy_with_pascal_style_folders_is_paired_without_assuming_the_official_layout(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", bmc=False, rdd2022_layout="voc_pascal")
    first = kr.run_dataset(cfg_for(tmp_path / "a", root), "rdd2022")
    assert first["status"] == "NEEDS_CONFIG" and stage(first, "profile_images")["detail"]["format_candidates"] == ["voc"]
    res = kr.run_dataset(cfg_for(tmp_path / "b", root, image={"rdd2022": {"format": "voc", "group_by": "block", "block_size": 5, "holdout_fraction": 0.5, "holdout_seed": 1}}), "rdd2022")
    assert res["status"] == "OK" and stage(res, "prepare")["detail"]["adapter_stats"]["annotated"] == 40
    assert stage(res, "group_audit")["detail"]["groups_straddling_train_and_holdout"] == 0 and res["real_holdout_readiness"]["annotated_holdout_images"] > 0


def test_rdd2022_multi_country_copy_needs_an_explicit_countries_filter_for_the_india_subset(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", bmc=False, rdd2022_countries=("India", "Japan", "Norway"))
    prof = stage(kr.run_dataset(cfg_for(tmp_path / "a", root), "rdd2022"), "profile_images")["detail"]
    assert prof["country_markers_images"] == {"india": 40, "japan": 40, "norway": 40} and any("countries" in w for w in prof["warnings"])
    cfg = cfg_for(tmp_path / "b", root, image={"rdd2022": {**VOC_CFG["rdd2022"], "countries": ["India"]}})
    res = kr.run_dataset(cfg, "rdd2022")
    recs = [json.loads(ln) for ln in (cfg.out / "rdd2022" / "prepared" / "records.jsonl").read_text(encoding="utf-8").splitlines()]
    assert res["status"] == "OK" and len(recs) == 40 and {r["country"] for r in recs} == {"India"}
    assert stage(res, "prepare")["detail"]["adapter_stats"]["filtered_out_by_country"] == 80
    none = kr.run_dataset(cfg_for(tmp_path / "c", root, image={"rdd2022": {**VOC_CFG["rdd2022"], "countries": ["Brazil"]}}), "rdd2022")
    assert none["status"] == "BLOCKED" and "matched nothing" in stage(none, "prepare_result")["detail"] and "india" in stage(none, "prepare_result")["detail"]


def test_same_stem_annotations_in_several_folders_are_resolved_by_path_or_left_unannotated_never_guessed(tmp_path):
    root = tmp_path / "in" / "rdd-2022"
    for country in ("India", "Czech"):                              # identical file stems in two country folders
        write_voc(root, country, "train", "IMG_1", [("D40", 1, 1, 9, 9)], with_image=False)
        make_real_jpeg(root / country / "train" / "images" / "IMG_1.jpg", 3 if country == "India" else 90)
    write_voc(root, "Norway", "train", "IMG_2", [("D40", 1, 1, 9, 9)], with_image=False)
    write_voc(root, "Japan", "train", "IMG_2", [("D00", 1, 1, 9, 9)], with_image=False)
    make_real_jpeg(root / "flat" / "IMG_2.jpg", 5)                  # sits in NEITHER country folder: ambiguous
    cfg = cfg_for(tmp_path, tmp_path / "in", image={"rdd2022": {"format": "voc"}})
    res = kr.run_dataset(cfg, "rdd2022")
    st = stage(res, "prepare")["detail"]["adapter_stats"]
    assert st["ambiguous_annotation_match"] == 1 and st["annotated"] == 2                       # the two IMG_1 images resolved by their own folder; flat/IMG_2 not guessed
    assert stage(res, "annotation_matching")["status"] == "warning"


def test_rdd2022_images_only_or_wrong_format_is_blocked_with_a_diagnosis(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", bmc=False, rdd2022_layout="images_only")
    first = kr.run_dataset(cfg_for(tmp_path / "a", root), "rdd2022")
    assert first["status"] == "NEEDS_CONFIG" and stage(first, "profile_images")["detail"]["format_candidates"] == []
    assert any("no annotation format recognised" in w for w in stage(first, "profile_images")["detail"]["warnings"])
    wrong = kr.run_dataset(cfg_for(tmp_path / "b", root, image={"rdd2022": {"format": "voc"}}), "rdd2022")      # operator insists on VOC: there are no xml files
    assert wrong["status"] == "BLOCKED" and "NO image matched an annotation file" in stage(wrong, "prepare_result")["detail"]
    assert stage(wrong, "annotation_format")["status"] == "warning"


def test_unsupported_annotation_formats_are_refused_clearly(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", bmc=False, rdd2022_layout="yolo_split")
    res = kr.run_dataset(cfg_for(tmp_path, root, image={"rdd2022": {"format": "tfrecord"}}), "rdd2022")
    assert res["status"] == "NEEDS_CONFIG" and "unsupported annotation format 'tfrecord'" in stage(res, "annotation_format")["detail"] and "voc" in res["next_steps"][0]


def test_a_corrupt_archive_is_reported_precisely_not_guessed_at(tmp_path):
    root = tmp_path / "in"
    make_rdd_copy(root / "rdd-2022", "archives_only")                      # a 4-byte "PK.." file named RDD2022.zip
    res = kr.run_dataset(cfg_for(tmp_path, root), "rdd2022")
    assert res["status"] == "BLOCKED" and "cannot be read" in res["next_steps"][0] and "RDD2022.zip" in res["next_steps"][0]
    assert not list((tmp_path / "work").rglob("records.jsonl")) and not (tmp_path / "work" / "extracted").exists()


def test_rdd2022_voc_first_run_end_to_end_with_licence_conflict_and_claim_blockers(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", bmc=False)
    cfg = cfg_for(tmp_path, root, image=VOC_CFG)
    res = kr.run_dataset(cfg, "rdd2022")
    assert res["status"] == "OK" and res["card"]["licence_status"] == "UNVERIFIED" and res["card"]["licence_conflicts"]
    assert list(stage(res, "card_provenance")["detail"]["execution_source"]) == ["https://www.kaggle.com/datasets/aliabdelmenam/rdd-2022"]
    rd = res["real_holdout_readiness"]
    assert rd["annotated_holdout_images"] > 0 and rd["publishable_evaluation_enabled"] is False
    cb = " ".join(rd["claim_blockers"])
    assert "licence not verified" in cb and "< 200" in cb
    files = stage(res, "image_file_and_duplicate_audit")["detail"]
    assert files["formats_by_magic_bytes"] == {"jpeg": 40} and files["near_duplicates"]["status"] == "ok"
    assert stage(res, "provider_vision_evaluation")["status"] == "not_requested"


def test_rdd2020_is_a_separate_run_with_its_own_card_and_ids(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", bmc=False, rdd2022=False, rdd2020=True)
    cfg = cfg_for(tmp_path, root, image={"rdd2020": {"format": "voc", "countries": ["India"]}})
    res = kr.run_dataset(cfg, "rdd2020")
    assert res["status"] == "OK" and "NonCommercial" in res["card"]["licence_name"]
    ids = [json.loads(ln)["record_id"] for ln in (cfg.out / "rdd2020" / "prepared" / "records.jsonl").read_text(encoding="utf-8").splitlines()]
    assert ids and all(i.startswith("rdd2020:") for i in ids)
    assert kr.run_dataset(cfg, "rdd2022")["status"] == "NOT_ATTACHED"


# ------------------------------------------------------------------ BharatPotHole: nothing assumed
def test_bharatpothole_stops_at_profile_until_format_and_class_names_are_given(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", bmc=False, rdd2022=False, bharat=True)
    cfg = cfg_for(tmp_path, root)
    r1 = kr.run_dataset(cfg, "bharatpothole")
    assert r1["status"] == "NEEDS_CONFIG" and stage(r1, "profile_images")["detail"]["n_images"] == 30
    assert "yolo" in stage(r1, "profile_images")["detail"]["format_candidates"] and "never guesses" in stage(r1, "annotation_format")["detail"]
    assert "'class_names_file': 'classes.txt'" in r1["next_steps"][0]                        # a suggestion is PRINTED, not applied
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
    assert r1["status"] == "NEEDS_CONFIG" and "folder" in stage(r1, "profile_images")["detail"]["format_candidates"]
    assert list(stage(r1, "card_provenance")["detail"]["execution_source"]) == ["https://data.mendeley.com/datasets/tj2m7zz4rg/2"]
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
    cfg = cfg_for(tmp_path, root, image={**VOC_CFG, "bharatpothole": {"format": "yolo", "class_names_file": "classes.txt"}})
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
    s = kr.run_all(cfg_for(tmp_path, root, image=VOC_CFG), ("bmc_mumbai", "rdd2022"))
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
    cfgf.write_text(json.dumps({"image": VOC_CFG}), encoding="utf-8")
    rc = kr.main(["--input-root", str(root), "--work-dir", str(tmp_path / "w"), "--datasets", "bmc_mumbai", "rdd2022", "--accept-terms", "bmc_mumbai", "rdd2022",
                  "--acknowledge-unverified-license", "--config", str(cfgf)])
    assert rc == 0 and (tmp_path / "w" / "civic_real_aggregates.zip").is_file()


# ================================================================== final preflight: the exact datasets and the guarantees around them
def tree_snapshot(root):
    return sorted((str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in root.rglob("*") if p.is_file())


def test_bmc_test_file_is_never_opened_or_read(tmp_path, monkeypatch):
    import builtins
    import pathlib
    opened: list[str] = []
    real_open, real_path_open = builtins.open, pathlib.Path.open

    def spy_open(file, *a, **k):
        opened.append(str(file))
        return real_open(file, *a, **k)

    def spy_path_open(self, *a, **k):
        opened.append(str(self))
        return real_path_open(self, *a, **k)
    root = make_fake_kaggle_input(tmp_path / "in", rdd2022=False)
    monkeypatch.setattr(builtins, "open", spy_open)
    monkeypatch.setattr(pathlib.Path, "open", spy_path_open)
    res = kr.run_dataset(cfg_for(tmp_path, root), "bmc_mumbai")
    assert res["status"] == "OK"
    assert any(p.endswith("bmc_train.csv") for p in opened) and any(p.endswith("bmc_data_dictionary.csv") for p in opened)
    assert not any(pathlib.Path(p).name == "bmc_test.csv" for p in opened)
    assert "test files are never opened" in stage(res, "select_data_file")["detail"]
    refused = kr.run_dataset(cfg_for(tmp_path / "x", root, files={"bmc_mumbai": str(next(root.rglob("bmc_test.csv")))}), "bmc_mumbai")
    assert refused["status"] == "NEEDS_CONFIG" and "TEST file" in refused["next_steps"][0]


def test_bmc_data_dictionary_is_summarised_and_compared_with_the_training_header(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", rdd2022=False)
    res = kr.run_dataset(cfg_for(tmp_path, root), "bmc_mumbai")
    dd = stage(res, "data_dictionary")["detail"]
    assert dd["file"] == "bmc_data_dictionary.csv" and dd["entries"] == 3 and dd["listed_names_missing_from_training_file"] == ["NOT_IN_TRAIN"]
    assert "UNCLASSIFIED_SENTINEL_COL" in dd["training_columns_not_listed_in_dictionary"]


def _renamed_bmc(root):
    """Use the reported real column names: complaint_status and resolution_days (post-resolution!) instead of status/resolution_date."""
    import csv
    f = next(root.rglob("bmc_train.csv"))
    rows = list(csv.DictReader(f.open(encoding="utf-8")))
    out = []
    for i, r in enumerate(rows):
        r = dict(r)
        r["complaint_status"] = r.pop("status")
        r.pop("resolution_date")
        r["resolution_days"] = str((i % 9) + 1) if r["complaint_status"] == "Closed" else ""
        out.append(r)
    with f.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)


def test_bmc_complaint_status_and_resolution_days_are_post_resolution_and_never_inputs(tmp_path):
    from ai.training.src.data_sources.column_roles import TaskPolicy
    pol = TaskPolicy.load("bmc_mumbai")
    assert pol.roles["status"].phase == "post_resolution" and pol.roles["resolution_duration"].phase == "post_resolution"
    for t, spec in pol.tasks.items():
        if spec.purpose != "demo":
            assert "status" not in spec.inputs and "resolution_duration" not in spec.inputs and "resolution_hours" not in spec.inputs and "closed_at" not in spec.inputs, t
    assert "resolution_hours" in pol.tasks["resolution_time_prior"].targets                                # a TARGET only, with a post-triage input ceiling
    root = make_fake_kaggle_input(tmp_path / "in", rdd2022=False)
    _renamed_bmc(root)
    no_unit = kr.run_dataset(cfg_for(tmp_path / "a", root), "bmc_mumbai")
    roles = stage(no_unit, "profile_and_role_validation")["detail"]["resolved_roles"]
    assert roles["status"] == "complaint_status" and roles["resolution_duration"] == "resolution_days"
    assert any("resolution_days" in n and "RESOLUTION_UNIT" in n for n in no_unit["next_steps"])           # unit is asked for, not assumed
    assert stage(no_unit, "synthetic_evaluation")["detail"]["resolution_time_prior"]["ran"] is False
    with_unit = kr.run_dataset(cfg_for(tmp_path / "b", root, resolution_unit="days"), "bmc_mumbai")
    assert with_unit["status"] == "OK" and stage(with_unit, "synthetic_evaluation")["detail"]["resolution_time_prior"]["ran"] is True
    rep = json.loads((tmp_path / "b" / "work" / "civic_real" / "bmc_mumbai" / "results" / "bmc_mumbai_resolution_time_prior.json").read_text(encoding="utf-8"))
    assert "status" not in rep["results"]["inputs_used"] and rep["track"] == "synthetic" and "THIRD-PARTY SYNTHETIC" in rep["claims"]["banner"]
    recs = (tmp_path / "b" / "work" / "civic_real" / "bmc_mumbai" / "prepared" / "records.jsonl").read_text(encoding="utf-8")
    assert "complaint_status" not in recs and '"status":"Closed"' in recs                                    # stored only as the descriptive source status field, never a model input


def test_the_whole_run_never_modifies_the_read_only_input_tree(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", bharat=True, nashik=True, rdd2020=True, rdd2022_countries=("India", "Japan"))
    before = tree_snapshot(root)
    cfg = cfg_for(tmp_path, root, image={**VOC_CFG, "rdd2020": {"format": "voc"}, "bharatpothole": {"format": "yolo", "class_names_file": "classes.txt"},
                                         "mumbai_nashik_road_surface": {"format": "folder"}})
    kr.run_all(cfg)
    kr.bundle(cfg)
    assert tree_snapshot(root) == before
    assert not any(str(p).startswith(str(root)) for p in cfg.out.rglob("*"))                                 # all outputs live under work_dir, none under the input root


def test_everything_runs_without_credentials_gpu_or_a_model_provider(tmp_path, monkeypatch):
    for k in ("OPENAI_API_KEY", "AI_INTAKE_MODEL", "AI_EMBEDDING_MODEL", "CUDA_VISIBLE_DEVICES", "HF_TOKEN", "KAGGLE_KEY"):
        monkeypatch.delenv(k, raising=False)
    import ai.evaluation.run_eval as re_
    monkeypatch.setattr(re_, "build_intake_system", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no provider/classifier may be built in a profile/audit run")))
    root = make_fake_kaggle_input(tmp_path / "in", bharat=True, nashik=True, rdd2020=True)
    cfg = cfg_for(tmp_path, root, image={**VOC_CFG, "rdd2020": {"format": "voc"}, "bharatpothole": {"format": "yolo", "class_names_file": "classes.txt"},
                                         "mumbai_nashik_road_surface": {"format": "folder"}})
    s = kr.run_all(cfg)
    assert {v["status"] for v in s["datasets"].values()} == {"OK"}
    s_ds = s["datasets"]
    for d in (x for x in s_ds if x != "bmc_mumbai"):
        assert stage(json.loads((cfg.out / d / "report.json").read_text(encoding="utf-8")), "provider_vision_evaluation")["status"] == "not_requested"


def test_without_pillow_the_run_completes_and_says_the_near_duplicate_audit_did_not_run(tmp_path, monkeypatch):
    from ai.training.src.data_sources import image_audit
    root = make_fake_kaggle_input(tmp_path / "in", bmc=False)
    monkeypatch.setattr(image_audit, "_pillow", lambda: None)
    res = kr.run_dataset(cfg_for(tmp_path, root, image=VOC_CFG), "rdd2022")
    assert res["status"] == "OK"
    st = stage(res, "image_file_and_duplicate_audit")
    assert st["status"] == "warning" and st["detail"]["near_duplicates"]["status"] == "unavailable"
    assert any("pip install pillow" in n and "NOT run" in n for n in res["next_steps"])


def test_one_bad_dataset_among_five_does_not_stop_the_rest_and_every_status_is_controlled(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", bharat=True, nashik=True, rdd2020=True)
    (root / "rdd2020-india" / "India" / "train" / "annotations" / "xmls" / "India_000001.xml").write_text("not xml at all", encoding="utf-8")      # corrupt annotation
    f = next(root.rglob("bmc_train.csv"))
    (f.parent / "bmc_train_copy.csv").write_text("a\n1\n", encoding="utf-8")                                                                       # ambiguous CSV
    cfg = cfg_for(tmp_path, root, image={"rdd2022": {"format": "tfrecord"}, "rdd2020": {"format": "voc"}, "bharatpothole": {"format": "yolo"}})   # unsupported / needs class names
    s = kr.run_all(cfg)
    st = {k: v["status"] for k, v in s["datasets"].items()}
    assert st == {"bmc_mumbai": "NEEDS_CONFIG", "mumbai_nashik_road_surface": "NEEDS_CONFIG", "rdd2022": "NEEDS_CONFIG", "rdd2020": "OK", "bharatpothole": "NEEDS_CONFIG"}
    assert set(st.values()) <= set(kr.STATUSES)
    assert all(v["next_steps"] for k, v in s["datasets"].items() if v["status"] != "OK")                       # every non-OK status carries actionable diagnostics
    assert stage(report(cfg, "rdd2020"), "prepare")["detail"]["adapter_stats"]["invalid_files"] == 1          # the corrupt annotation was counted, not fatal


def test_a_single_attached_dataset_runs_alone(tmp_path):
    for name, kw, cfg_img in (("bharatpothole", {"bharat": True}, {"bharatpothole": {"format": "yolo", "class_names_file": "classes.txt"}}),
                              ("mumbai_nashik_road_surface", {"nashik": True}, {"mumbai_nashik_road_surface": {"format": "folder"}})):
        root = make_fake_kaggle_input(tmp_path / name / "in", bmc=False, rdd2022=False, **kw)
        s = kr.run_all(cfg_for(tmp_path / name, root, image=cfg_img))
        assert s["datasets"][name]["status"] == "OK"
        assert {v["status"] for k, v in s["datasets"].items() if k != name} == {"NOT_ATTACHED"}


def test_bundle_is_an_allowlist_and_refuses_oversized_or_unknown_files(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", bharat=True)
    cfg = cfg_for(tmp_path, root, image={**VOC_CFG, "bharatpothole": {"format": "yolo", "class_names_file": "classes.txt"}})
    kr.run_all(cfg)
    (cfg.out / "bmc_mumbai" / "stray_rows.json").write_text('[{"row": 1}]', encoding="utf-8")                  # unknown name: not bundled
    (cfg.out / "bmc_mumbai" / "prepared" / "notes.md").write_text("x", encoding="utf-8")
    names = zipfile.ZipFile(kr.bundle(cfg)).namelist()
    assert "bmc_mumbai/stray_rows.json" not in names and "bmc_mumbai/prepared/notes.md" not in names
    assert "bmc_mumbai/prepared/PREPARE_MANIFEST.json" in names and "SUMMARY.json" in names
    assert not any(n.endswith(("records.jsonl", ".csv", ".jpg", ".png", ".mp4", ".xml", ".txt", ".parquet")) for n in names)
    big = cfg.out / "bmc_mumbai" / "report.json"
    big.write_text(big.read_text(encoding="utf-8") + " " * (kr.BUNDLE_MAX_FILE_BYTES + 10), encoding="utf-8")
    with pytest.raises(DataSourceError, match="refusing to bundle"):
        kr.bundle(cfg)


def test_summary_records_the_executed_repo_ref_and_commit(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in")
    meta = {"requested_url": "https://example.invalid/repo", "requested_ref": "claude/epic-fermat-3qlw5c", "commit": "a" * 40, "source": "git checkout"}
    cfg = cfg_for(tmp_path, root, meta=meta, image=VOC_CFG)
    kr.run_all(cfg, ("bmc_mumbai",))
    assert json.loads((cfg.out / "SUMMARY.json").read_text(encoding="utf-8"))["repo"] == meta
    assert f"@ `claude/epic-fermat-3qlw5c` · commit `{'a' * 40}`" in (cfg.out / "SUMMARY.md").read_text(encoding="utf-8")


def test_real_style_bmc_headers_enable_routing_and_flag_the_uncomputable_recurrence(tmp_path):
    import csv
    root = make_fake_kaggle_input(tmp_path / "in", rdd2022=False)
    f = next(root.rglob("bmc_train.csv"))
    rows = list(csv.DictReader(f.open(encoding="utf-8")))
    with f.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["department_assigned" if h == "department" else h for h in rows[0] if h not in ("latitude", "longitude")])
        w.writeheader()
        for r in rows:
            r = {("department_assigned" if k == "department" else k): v for k, v in r.items() if k not in ("latitude", "longitude")}
            w.writerow(r)
    res = kr.run_dataset(cfg_for(tmp_path, root), "bmc_mumbai")
    assert res["status"] == "OK"
    assert stage(res, "profile_and_role_validation")["detail"]["resolved_roles"]["department"] == "department_assigned"
    ev = stage(res, "synthetic_evaluation")["detail"]
    assert ev["routing_agreement"]["ran"] is True                                                         # it was skipped before the alias existed
    assert ev["recurrence_hotspot"]["ran"] is True and ev["recurrence_hotspot"]["meaningful"] is False and "coordinates" in ev["recurrence_hotspot"]["not_computable_because"]
    assert any("recurrence_hotspot is NOT computable" in n for n in res["next_steps"])
