"""Indian road-image sources: generic detection adapter, group-safe holdouts, image profiling, RDD2020, vision eval plumbing.

All trees are tiny INVENTED directory layouts with fake image bytes: they prove format handling and leakage protections,
not what the real BharatPotHole / Mumbai-Nashik / RDD files look like (never seen here; see the source cards).
"""
import json

import pytest

from ai.training.src.data_sources import cli
from ai.training.src.data_sources import prepare as prep
from ai.training.src.data_sources.adapters.detection import DetectionDatasetAdapter, load_class_names
from ai.training.src.data_sources.canonical import ImageRecord
from ai.training.src.data_sources.card_schema import load_card
from ai.training.src.data_sources.errors import DataSourceError, SchemaMismatch
from ai.training.src.data_sources.image_profile import profile_image_dataset
from ai.training.src.data_sources.mapping import MappingTable
from ai.training.src.io_utils import read_jsonl

from .conftest_real import make_rdd_tree, write_voc

JPG = b"\xff\xd8\xff\xe0FAKEJPEG"


def img(root, rel):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(JPG)
    return p


def adapter(card_id, **kw):
    card = load_card(card_id)
    return DetectionDatasetAdapter(card, MappingTable.load(card.mapping_id), retrieved_at="2026-10-01", **kw)


def yolo_tree(root, videos=3, frames=4):
    """images/vidN_fK.jpg + labels/vidN_fK.txt, class ids 0=pothole 1=speedbump."""
    for v in range(videos):
        for f in range(frames):
            img(root, f"images/vid{v}_f{f}.jpg")
            (root / "labels").mkdir(exist_ok=True)
            (root / "labels" / f"vid{v}_f{f}.txt").write_text("0 0.5 0.5 0.2 0.2\n1 0.3 0.3 0.1 0.1\n9 0.1 0.1 0.1 0.1\n", encoding="utf-8")
    img(root, "images/vid9_f0.jpg")          # no label file
    return root


# ------------------------------------------------------------------ explicit formats; nothing guessed
def test_format_is_mandatory_and_must_be_known():
    card = load_card("bharatpothole")
    with pytest.raises(SchemaMismatch, match="format"):
        DetectionDatasetAdapter(card, MappingTable.load(card.mapping_id), fmt="auto")  # type: ignore[arg-type]
    with pytest.raises(SchemaMismatch):
        adapter("bharatpothole", fmt="yolo", class_names=None)
    with pytest.raises(SchemaMismatch, match="regex"):
        adapter("bharatpothole", fmt="voc", group_by="regex")
    with pytest.raises(SchemaMismatch):
        adapter("bharatpothole", fmt="voc", group_by="nonsense")


def test_missing_root_is_loud(tmp_path):
    with pytest.raises(SchemaMismatch, match="not found"):
        list(adapter("bharatpothole", fmt="voc").iter_records(tmp_path / "nope"))


def test_yolo_uses_the_datasets_own_class_names_and_never_guesses_unknown_ids(tmp_path):
    root = yolo_tree(tmp_path / "ds")
    ad = adapter("bharatpothole", fmt="yolo", class_names=["pothole", "speedbump"], group_by="regex", group_regex=r"^(vid\d+)_")
    recs = list(ad.iter_records(root))
    assert len(recs) == 13 and ad.stats["unknown_class_ids"] == 12 and ad.stats["unannotated_no_label_file"] == 1
    r = next(x for x in recs if x.record_id.endswith("vid0_f0"))
    assert [b.class_code for b in r.boxes] == ["pothole", "speedbump"] and all(b.normalized for b in r.boxes)
    assert r.image_labels == ["roads/pothole"] and r.group_id == "vid0" and r.provenance.label_origin == "human_annotated"
    assert next(b for b in r.boxes if b.class_code == "speedbump").mapping_status == "unmapped"
    unl = next(x for x in recs if x.record_id.endswith("vid9_f0"))
    assert unl.has_annotation is False and unl.boxes == [] and unl.image_labels == []


def test_only_the_exact_pothole_class_maps_other_classes_are_not_invented_into_the_taxonomy():
    m = MappingTable.load("bharatpothole_to_civic")
    assert (m.map(class_name="pothole").category, m.map(class_name="pothole").subcategory) == ("roads", "pothole")
    assert m.map(class_name="Potholes").status == "exact"
    for other in ("crack", "speedbump", "manhole", "D00", "road"):
        assert m.map(class_name=other).status in ("unmapped", "out_of_scope"), other


def test_voc_images_without_xml_are_unannotated_not_negatives_and_bad_xml_is_counted(tmp_path):
    root = tmp_path / "v"
    write_voc(root, "a", "train", "i1", [("pothole", 1, 1, 50, 60)])
    write_voc(root, "a", "train", "i2", [("pothole", 5, 5, 5, 5)])
    write_voc(root, "a", "train", "bad", [], raw="<!DOCTYPE x [<!ENTITY a 'b'>]><annotation/>", with_image=True)
    img(root, "a/train/images/naked.jpg")
    ad = adapter("bharatpothole", fmt="voc")
    recs = {r.record_id.split(":", 1)[1].split("/")[-1]: r for r in ad.iter_records(root)}
    assert recs["i1"].image_labels == ["roads/pothole"] and recs["i1"].boxes[0].normalized is False
    assert recs["i2"].boxes == [] and ad.stats["degenerate_boxes"] == 1 and recs["naked"].has_annotation is False
    assert "bad" not in recs and ad.stats["invalid_files"] == 1


def test_coco_resolves_categories_by_name_and_reports_unknown_ids(tmp_path):
    root = tmp_path / "c"
    img(root, "imgs/a.jpg")
    img(root, "imgs/b.jpg")
    (root / "ann.json").write_text(json.dumps({
        "images": [{"id": 1, "file_name": "imgs/a.jpg", "width": 10, "height": 10}, {"id": 2, "file_name": "b.jpg"}, {"id": 3, "file_name": "ghost.jpg"}],
        "categories": [{"id": 5, "name": "pothole"}, {"id": 6, "name": "crack"}],
        "annotations": [{"image_id": 1, "category_id": 5, "bbox": [1, 1, 4, 4]}, {"image_id": 1, "category_id": 99, "bbox": [1, 1, 4, 4]},
                        {"image_id": 2, "category_id": 6, "bbox": [0, 0, 2, 2]}]}), encoding="utf-8")
    ad = adapter("bharatpothole", fmt="coco", group_by="none")
    recs = {r.image_relpath: r for r in ad.iter_records(root)}
    assert recs["imgs/a.jpg"].image_labels == ["roads/pothole"] and ad.stats["unknown_class_ids"] == 1 and ad.stats["coco_files"] == 1
    assert recs["imgs/b.jpg"].image_labels == [] and recs["imgs/b.jpg"].boxes[0].mapping_status == "unmapped"      # found by file name, crack stays unmapped
    assert "ghost.jpg" in recs                                                                                     # unresolved name is kept as written
    empty = tmp_path / "no_json"
    img(empty, "x.jpg")
    with pytest.raises(SchemaMismatch, match="COCO"):
        list(adapter("bharatpothole", fmt="coco").iter_records(empty))


def test_folder_labels_come_from_directory_names_and_scene_attributes_are_not_taxonomy_categories(tmp_path):
    root = tmp_path / "f"
    for rel in ("Paved Road/p1.jpg", "Paved Road/p2.jpg", "Unpaved Road/u1.jpg", "damaged_road/d1.jpg", "pothole/h1.jpg", "speed breaker/s1.jpg", "loose.jpg"):
        img(root, rel)
    ad = adapter("mumbai_nashik_road_surface", fmt="folder")
    by = {r.image_relpath: r for r in ad.iter_records(root)}
    assert by["pothole/h1.jpg"].image_labels == ["roads/pothole"]
    assert by["damaged_road/d1.jpg"].image_labels == ["roads"]                     # category-level only; NOT a pothole
    for oos in ("Paved Road/p1.jpg", "Unpaved Road/u1.jpg", "speed breaker/s1.jpg"):
        assert by[oos].image_labels == [] and by[oos].has_annotation, oos
    assert by["loose.jpg"].has_annotation is False
    assert {c for r in by.values() for c in r.image_labels} <= {"roads", "roads/pothole"}                 # no invented categories


def test_label_from_top_or_all_changes_which_path_component_is_the_label(tmp_path):
    root = tmp_path / "t"
    img(root, "pothole/Paved Road/x.jpg")
    for lf, expect in (("parent", ["Paved Road"]), ("top", ["pothole"]), ("all", ["Paved Road", "pothole"])):
        (r,) = list(adapter("mumbai_nashik_road_surface", fmt="folder", label_from=lf).iter_records(root))
        assert r.source_labels == sorted(expect), lf


def test_mumbai_nashik_mapping_never_creates_a_new_v1_category():
    m = MappingTable.load("mumbai_nashik_to_civic")
    cats = {r.get("category") for r in m.raw["rules"]} - {None}
    assert cats == {"roads"}
    assert "hypothesised" in m.raw["status"].lower() or "not_verified" in m.raw["status"].lower()


# ------------------------------------------------------------------ class-name files
@pytest.mark.parametrize("name,text,expect", [
    ("classes.txt", "pothole\n\nspeedbump\n", ["pothole", "speedbump"]),
    ("obj.names", "a\nb\n", ["a", "b"]),
    ("c.json", json.dumps(["x", "y"]), ["x", "y"]),
    ("c2.json", json.dumps({"names": {"1": "b", "0": "a"}}), ["a", "b"]),
    ("data.yaml", "nc: 2\nnames: ['pothole', \"crack\"]\n", ["pothole", "crack"]),
    ("data2.yaml", "nc: 2\nnames:\n  0: pothole\n  1: crack\n", ["pothole", "crack"]),
    ("data3.yml", "names:\n  - pothole\n  - crack\n", ["pothole", "crack"]),
])
def test_load_class_names_variants(tmp_path, name, text, expect):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    assert load_class_names(p) == expect


def test_load_class_names_errors_are_loud(tmp_path):
    with pytest.raises(SchemaMismatch, match="not found"):
        load_class_names(tmp_path / "missing.txt")
    p = tmp_path / "bad.yaml"
    p.write_text("train: x\n", encoding="utf-8")
    with pytest.raises(SchemaMismatch, match="names"):
        load_class_names(p)


# ------------------------------------------------------------------ group rules (leakage between frames of one video)
def test_group_rules_dir_regex_block_none(tmp_path):
    root = tmp_path / "g"
    for rel in ("seqA/frame_001.jpg", "seqA/frame_002.jpg", "seqB/frame_150.jpg", "seqB/frame_199.jpg", "seqB/noindex.jpg"):
        img(root, rel)
    groups = lambda **kw: {r.image_relpath: r.group_id for r in adapter("bharatpothole", fmt="folder", **kw).iter_records(root)}  # noqa: E731
    assert groups(group_by="dir")["seqA/frame_001.jpg"] == "seqA" == groups(group_by="dir")["seqA/frame_002.jpg"]
    b = groups(group_by="block", block_size=100)
    assert b["seqA/frame_001.jpg"] == b["seqA/frame_002.jpg"] == "seqA:0" and b["seqB/frame_150.jpg"] == b["seqB/frame_199.jpg"] == "seqB:1"
    assert b["seqB/noindex.jpg"] is None
    assert set(groups(group_by="none").values()) == {None}
    ad2 = adapter("bharatpothole", fmt="folder", group_by="regex", group_regex=r"frame_(\d)")
    got = {r.image_relpath: r.group_id for r in ad2.iter_records(root)}
    assert got["seqA/frame_001.jpg"] == "0" and ad2.stats["group_unparsed"] == 1


# ------------------------------------------------------------------ prepare_images: group-safe holdout, honesty about positives
def test_prepare_images_holdout_keeps_whole_groups_together(tmp_path):
    root = yolo_tree(tmp_path / "ds", videos=12, frames=5)
    names = tmp_path / "classes.txt"
    names.write_text("pothole\nspeedbump\n", encoding="utf-8")
    m = prep.prepare_images(load_card("bharatpothole"), root, tmp_path / "out", fmt="yolo", class_names_file=names, group_by="regex",
                            group_regex=r"^(vid\d+)_", holdout_fraction=0.4, holdout_seed=3, retrieved_at="2026-10-01")
    assert m["split_straddle"]["straddling_groups"] == 0 and m["split_counts"].get("holdout", 0) > 0 and m["split_counts"].get("train", 0) > 0
    recs = [ImageRecord.model_validate(r) for r in read_jsonl(tmp_path / "out" / "records.jsonl")]
    side = {}
    for r in recs:
        if r.group_id:
            side.setdefault(r.group_id, set()).add(r.split_hint)
    assert all(len(v) == 1 for v in side.values())
    assert m["license_verified"] is False and m["license_status"] == "UNVERIFIED" and m["origin_verified"] is True
    assert "NOT permitted" in m["redistribution"] and m["images_without_group"] == 0 and m["n_groups"] == 13 - 1
    assert m["adapter_stats"]["unknown_class_ids"] > 0 and m["options"]["class_names_file"] == "classes.txt"


def test_holdout_without_a_group_rule_is_refused(tmp_path):
    root = tmp_path / "f"
    img(root, "pothole/a.jpg")
    with pytest.raises(DataSourceError, match="group rule"):
        prep.prepare_images(load_card("bharatpothole"), root, tmp_path / "o", fmt="folder", group_by="none", holdout_fraction=0.3)


def test_positive_only_datasets_carry_a_precision_warning(tmp_path):
    root = tmp_path / "pos"
    for i in range(5):
        img(root, f"pothole/p{i}.jpg")
    m = prep.prepare_images(load_card("bharatpothole"), root, tmp_path / "o", fmt="folder")
    assert m["pothole_positive_share"] == 1.0 and "precision is not meaningful" in m["positive_only_warning"]
    root2 = tmp_path / "mixed"
    img(root2, "pothole/a.jpg")
    img(root2, "paved/b.jpg")
    assert prep.prepare_images(load_card("mumbai_nashik_road_surface"), root2, tmp_path / "o2", fmt="folder")["positive_only_warning"] is None


def test_non_detection_cards_cannot_use_the_generic_image_adapter(tmp_path):
    with pytest.raises(DataSourceError, match="generic image adapter"):
        prep.prepare_images(load_card("rdd2022"), tmp_path, tmp_path / "o", fmt="voc")


# ------------------------------------------------------------------ profile-images (facts and candidates, no decisions)
def test_profile_images_reports_candidates_and_warns_about_missing_class_names_videos_and_groups(tmp_path):
    root = yolo_tree(tmp_path / "ds")
    (root / "clip.mp4").write_bytes(b"x")
    rep = profile_image_dataset(root)
    assert rep["n_images"] == 13 and rep["n_videos"] == 1 and "yolo" in rep["format_candidates"]
    text = " ".join(rep["warnings"])
    assert "class-names" in text and "video" in text.lower() and "NOT decisions" in rep["note"]
    (root / "classes.txt").write_text("pothole\n", encoding="utf-8")
    assert "classes.txt" in profile_image_dataset(root)["class_name_files"]
    with pytest.raises(SchemaMismatch):
        profile_image_dataset(tmp_path / "missing")


def test_profile_images_flags_datasets_with_no_usable_group_structure(tmp_path):
    root = tmp_path / "flat"
    for n in ("alpha", "beta", "gamma"):
        img(root, f"{n}.jpg")
    assert any("group id" in w for w in profile_image_dataset(root)["warnings"])


# ------------------------------------------------------------------ CLI
ACCEPT_BP = ["--accept-terms", "bharatpothole", "--acknowledge-unverified-license"]


def test_cli_profile_images_then_prepare_requires_explicit_format_and_terms(tmp_path, capsys):
    root = tmp_path / "ds"
    for i in range(4):
        img(root, f"pothole/v{i}_001.jpg")
    assert cli.main(["profile-images", str(root), "--out", str(tmp_path / "p.json")]) == 0
    assert "format candidates (NOT decisions)" in capsys.readouterr().out
    base = ["prepare", "bharatpothole", "--input", str(root), "--out", str(tmp_path / "out")]
    assert cli.main(base) == 2 and "--accept-terms bharatpothole" in capsys.readouterr().err
    assert cli.main([*base, *ACCEPT_BP]) == 2 and "--format" in capsys.readouterr().err
    assert cli.main([*base, *ACCEPT_BP, "--format", "folder", "--group-by", "regex", "--group-regex", r"^(v\d+)_", "--holdout-fraction", "0.5"]) == 0
    m = json.loads((tmp_path / "out" / "PREPARE_MANIFEST.json").read_text(encoding="utf-8"))
    assert m["records"] == 4 and m["license_verified"] is False


def test_cli_prepare_mumbai_nashik_reports_unconfirmed_identity_and_idd_is_refused(tmp_path, capsys):
    root = tmp_path / "mn"
    img(root, "Paved Road/a.jpg")
    args = ["prepare", "mumbai_nashik_road_surface", "--input", str(root), "--out", str(tmp_path / "o"), "--accept-terms", "mumbai_nashik_road_surface",
            "--acknowledge-unverified-license", "--format", "folder"]
    assert cli.main(args) == 0
    assert json.loads((tmp_path / "o" / "PREPARE_MANIFEST.json").read_text(encoding="utf-8"))["identity_status"] == "CANDIDATE_NEEDS_CONFIRMATION"
    capsys.readouterr()
    rc = cli.main(["prepare", "idd", "--input", str(root), "--out", str(tmp_path / "i"), "--accept-terms", "idd", "--acknowledge-unverified-license"])
    assert rc == 2 and "not part of V1" in capsys.readouterr().err


# ------------------------------------------------------------------ RDD2020 reuses the RDD adapter without mixing ids or licences
def test_rdd2020_prepare_prefixes_ids_uses_its_own_card_and_keeps_test_splits_and_groups(tmp_path):
    root = make_rdd_tree(tmp_path / "RDD")
    for stem in ("IN_100", "IN_101", "IN_250"):
        write_voc(root, "India", "test1", stem, [("D40", 1, 1, 40, 40)])
    m = prep.prepare_rdd(load_card("rdd2020"), root, tmp_path / "out", countries={"India"}, include_unannotated=True, holdout_countries=None)
    recs = [ImageRecord.model_validate(r) for r in read_jsonl(tmp_path / "out" / "records.jsonl")]
    assert recs and all(r.record_id.startswith("rdd2020:") for r in recs) and all(r.provenance.source_id == "rdd2020" for r in recs)
    assert m["source_id"] == "rdd2020" and "Non" in json.dumps(m["license_status"]) + load_card("rdd2020").license.name
    t1 = {r.record_id: r for r in recs if r.split_hint is None or "test1" in r.image_relpath}
    g = {r.image_relpath.rsplit("/", 1)[-1]: r.group_id for r in recs if "test1" in r.image_relpath}
    assert g["IN_100.jpg"] == g["IN_101.jpg"] != g["IN_250.jpg"] and t1


def test_rdd2020_and_rdd2022_cards_do_not_share_licence_claims():
    a, b = load_card("rdd2020"), load_card("rdd2022")
    assert a.license.name != b.license.name and "NonCommercial" in a.license.name and "NonCommercial" not in b.license.name
    assert a.license.status == "UNVERIFIED" and b.license.status == "UNVERIFIED"


# ------------------------------------------------------------------ vision evaluation plumbing (scripted provider; no network)
INTAKE_POTHOLE = {"title": "t", "description": "d", "category": "roads", "subcategory": "pothole", "severity": "LOW", "language": "en", "transcript": None,
                  "confidence": 0.9, "reasons": [], "image_observations": ["hole in the road"]}


def test_vision_eval_on_a_dataset_without_countries_groups_by_source_id_and_flags_all_pothole_precision(tmp_path):
    from ai.evaluation import eval_real
    from ai.inference.intake.service import IntakeService
    from ai.inference.providers.fake import FakeProvider
    root = tmp_path / "ds"
    for i in range(6):
        img(root, f"pothole/p{i}.jpg")
    prep.prepare_images(load_card("bharatpothole"), root, tmp_path / "o", fmt="folder")
    recs = read_jsonl(tmp_path / "o" / "records.jsonl")
    r = eval_real.evaluate_vision(IntakeService(FakeProvider(structured={"intake": INTAKE_POTHOLE})), recs, root)
    assert r["n"] == 6 and list(r["by_country"]) == ["bharatpothole"]
    assert r["overall"]["gold_pothole_rate"] == 1.0 and r["overall"]["pothole_precision_valid"] is False and r["overall"]["pothole_recall"] == 1.0
    assert "negatives" in r["precision_note"]
