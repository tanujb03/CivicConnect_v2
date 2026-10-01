"""Aggregate image audits: headers/dimensions, exact + near duplicates (and whether they straddle groups/splits), annotation/group audits."""
import hashlib
import struct

import pytest

from ai.training.src.data_sources import image_audit as ia
from ai.training.src.data_sources.canonical import BBox, ImageRecord, Provenance

pytest.importorskip("PIL", reason="Pillow builds the real test images (Kaggle images ship Pillow)")
from PIL import Image  # noqa: E402

from .conftest_real import make_real_jpeg  # noqa: E402


def rec(rid, rel, *, boxes=(), split=None, group=None, annotated=True, w=None, h=None, labels=None, source=None):
    p = Provenance(kind="real_public", source_id="x", source_dataset="X", license_id="L", license_verified=False, label_origin="human_annotated")
    bb = [BBox(class_code=c, xmin=a, ymin=b, xmax=d, ymax=e, category="roads" if c == "D40" else None, subcategory="pothole" if c == "D40" else None,
               mapping_status="exact" if c == "D40" else "unmapped") for c, a, b, d, e in boxes]
    return ImageRecord(record_id=rid, provenance=p, image_relpath=rel, width=w, height=h, has_annotation=annotated, boxes=bb,
                       image_labels=labels if labels is not None else (["roads/pothole"] if any(b.class_code == "D40" for b in bb) else []),
                       source_labels=source if source is not None else sorted({b.class_code for b in bb}), group_id=group, split_hint=split)


def test_headers_for_jpeg_png_bmp_and_junk(tmp_path):
    make_real_jpeg(tmp_path / "a.jpg", 1, size=(64, 48))
    Image.new("RGB", (30, 20)).save(tmp_path / "b.png")
    Image.new("RGB", (10, 12)).save(tmp_path / "c.bmp")
    (tmp_path / "junk.jpg").write_bytes(b"not an image at all")
    assert ia.read_image_header(tmp_path / "a.jpg") == {"format": "jpeg", "width": 64, "height": 48}
    assert ia.read_image_header(tmp_path / "b.png") == {"format": "png", "width": 30, "height": 20}
    assert ia.read_image_header(tmp_path / "c.bmp") == {"format": "bmp", "width": 10, "height": 12}
    assert ia.read_image_header(tmp_path / "junk.jpg")["format"] is None
    assert ia.read_image_header(tmp_path / "missing.jpg")["unreadable"] is True
    assert ia.sniff_format(b"\x89PNG\r\n\x1a\n....") == "png" and struct.calcsize(">II") == 8


def test_files_audit_reports_dimensions_formats_missing_and_extension_mismatch(tmp_path):
    for i in range(3):
        make_real_jpeg(tmp_path / f"i{i}.jpg", i + 1, size=(64, 48))
    make_real_jpeg(tmp_path / "wide.jpg", 9, size=(128, 48))
    Image.new("RGB", (8, 8), (255, 0, 0)).save(tmp_path / "png_named_jpg.jpg", "PNG")
    r = ia.image_files_audit(tmp_path, ["i0.jpg", "i1.jpg", "i2.jpg", "wide.jpg", "png_named_jpg.jpg", "ghost.jpg"])
    assert r["files_audited"] == 6 and r["missing_files"] == 1 and r["unreadable_files"] == 0
    assert r["formats_by_magic_bytes"] == {"jpeg": 4, "png": 1} and r["extension_vs_content_mismatch"] == {"jpg->png": 1}
    assert r["distinct_dimensions"] == 3 and r["top_dimensions"][0] == ("64x48", 3) and r["width"]["max"] == 128
    assert r["capped_to_first_n_by_path"] is False


def test_files_audit_cap_is_reported(tmp_path):
    for i in range(5):
        make_real_jpeg(tmp_path / f"i{i}.jpg", i + 1)
    r = ia.image_files_audit(tmp_path, [f"i{i}.jpg" for i in range(5)], max_files=2, max_near_dup_images=2)
    assert r["files_audited"] == 2 and r["files_total"] == 5 and r["capped_to_first_n_by_path"] is True
    assert r["near_duplicates"]["capped_to_first_n_by_path"] is True


def test_exact_duplicates_are_found_and_flagged_when_they_span_groups_and_splits(tmp_path):
    make_real_jpeg(tmp_path / "a.jpg", 5)
    (tmp_path / "b.jpg").write_bytes((tmp_path / "a.jpg").read_bytes())
    make_real_jpeg(tmp_path / "c.jpg", 77)
    group = {"a.jpg": "g1", "b.jpg": "g2", "c.jpg": "g1"}
    split = {"a.jpg": "train", "b.jpg": "holdout", "c.jpg": "train"}
    r = ia.image_files_audit(tmp_path, list(group), group_of=group.get, split_of=split.get)["exact_duplicates"]
    assert r["duplicate_clusters"] == 1 and r["files_in_duplicate_clusters"] == 2 and r["clusters_spanning_groups"] == 1 and r["clusters_spanning_train_and_holdout"] == 1
    assert hashlib.sha1((tmp_path / "a.jpg").read_bytes()).hexdigest() == hashlib.sha1((tmp_path / "b.jpg").read_bytes()).hexdigest()


def test_near_duplicates_are_found_across_a_split_and_distinct_images_are_not(tmp_path):
    base = Image.new("RGB", (64, 48))
    px = base.load()
    for x in range(64):
        for y in range(48):
            px[x, y] = (x * 4 % 256, y * 5 % 256, (x * y) % 256)
    base.save(tmp_path / "frame_a.jpg", "JPEG", quality=95)
    base.save(tmp_path / "frame_b.jpg", "JPEG", quality=70)                  # same scene, recompressed: a near duplicate, not a byte duplicate
    make_real_jpeg(tmp_path / "other.jpg", 123)
    group = {"frame_a.jpg": "v1", "frame_b.jpg": "v2", "other.jpg": "v3"}
    split = {"frame_a.jpg": "train", "frame_b.jpg": "holdout", "other.jpg": "train"}
    r = ia.image_files_audit(tmp_path, list(group), group_of=group.get, split_of=split.get)
    n = r["near_duplicates"]
    assert r["exact_duplicates"]["duplicate_clusters"] == 0
    assert n["status"] == "ok" and n["near_duplicate_pairs"] == 1 and n["images_with_a_near_twin"] == 2
    assert n["pairs_spanning_groups"] == 1 and n["pairs_spanning_train_and_holdout"] == 1 and n["examples"] == [["frame_a.jpg", "frame_b.jpg"]]


def test_without_pillow_the_near_duplicate_check_says_it_did_not_run(tmp_path, monkeypatch):
    make_real_jpeg(tmp_path / "a.jpg", 1)
    monkeypatch.setattr(ia, "_pillow", lambda: None)
    n = ia.image_files_audit(tmp_path, ["a.jpg"])["near_duplicates"]
    assert n["status"] == "unavailable" and "NOT run" in n["reason"]
    assert ia.dhash(tmp_path / "a.jpg") is None


def test_dhash_is_deterministic_and_undecodable_files_are_none(tmp_path):
    make_real_jpeg(tmp_path / "a.jpg", 4)
    (tmp_path / "bad.jpg").write_bytes(b"\xff\xd8\xffgarbage")
    assert ia.dhash(tmp_path / "a.jpg") == ia.dhash(tmp_path / "a.jpg") and ia.dhash(tmp_path / "bad.jpg") is None


def test_annotation_audit_counts_classes_missing_annotations_and_box_sizes():
    recs = [rec("1", "a.jpg", boxes=[("D40", 0, 0, 32, 24), ("D00", 0, 0, 64, 48)], w=64, h=48), rec("2", "b.jpg", boxes=[], w=64, h=48),
            rec("3", "c.jpg", annotated=False), rec("4", "d.jpg", boxes=[("D40", 0, 0, 16, 12)], w=64, h=48)]
    a = ia.annotation_audit(recs)
    assert a["images"] == 4 and a["annotated_images"] == 3 and a["images_without_annotation"] == 1 and a["annotated_images_with_no_boxes_or_labels"] == 1
    assert a["source_class_counts"] == {"D40": 2, "D00": 1} and a["mapped_box_label_counts"] == {"roads/pothole": 2, "(unmapped)": 1}
    assert a["mapping_status_by_source_class"] == {"D40": {"exact": 2}, "D00": {"unmapped": 1}}
    assert a["boxes_per_annotated_image"]["max"] == 2.0 and a["box_area_fraction_of_image"]["max"] == 1.0
    assert "NOT that the image shows a good road" in a["note"]


def test_annotation_audit_handles_folder_labels_without_boxes():
    r = rec("1", "x/pothole/a.jpg", source=["pothole"], labels=["roads/pothole"])
    a = ia.annotation_audit([r])
    assert a["source_class_counts"] == {"pothole": 1} and a["image_level_mapped_label_counts"] == {"roads/pothole": 1}


def test_group_audit_detects_groups_straddling_the_split():
    recs = [rec("1", "1.jpg", group="v1", split="train"), rec("2", "2.jpg", group="v1", split="holdout"), rec("3", "3.jpg", group="v2", split="train"),
            rec("4", "4.jpg", group=None, split="train")]
    g = ia.group_audit(recs)
    assert g["n_groups"] == 2 and g["images_without_group"] == 1 and g["singleton_groups"] == 1
    assert g["groups_straddling_train_and_holdout"] == 1 and g["straddle_examples"] == ["v1"] and g["split_counts"] == {"train": 3, "holdout": 1}


def test_video_frame_relationships_state_what_is_unknown():
    both = ia.video_frame_relationships({"n_videos": 13, "n_images": 8484, "numbered_filename_share": 0.2})
    assert "NOT established" in both["observations"][0]
    vid = ia.video_frame_relationships({"n_videos": 2, "n_images": 0})
    assert "extracted externally" in vid["observations"][0]
    seq = ia.video_frame_relationships({"n_videos": 0, "n_images": 100, "numbered_filename_share": 0.95})
    assert "block or regex" in seq["observations"][0]
    assert ia.video_frame_relationships({"n_videos": 0, "n_images": 10, "numbered_filename_share": 0.0})["observations"] == []
