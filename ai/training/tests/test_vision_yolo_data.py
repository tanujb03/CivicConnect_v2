"""Detector data preparation: group-safe splits, VOC->YOLO conversion, evidence-based decoding of numeric class ids, dataset assembly (INVENTED fixtures)."""
import random
from pathlib import Path

from PIL import Image

from ai.training.src.vision import yolo_data as yd

W, H = 640, 480


def write_img(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 48), (120, 120, 120)).save(p)


def write_voc(p: Path, stem: str, objs):
    body = "".join(f"<object><name>{n}</name><bndbox><xmin>{b[0]}</xmin><ymin>{b[1]}</ymin><xmax>{b[2]}</xmax><ymax>{b[3]}</ymax></bndbox></object>" for n, b in objs)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"<annotation><filename>{stem}.jpg</filename><size><width>{W}</width><height>{H}</height></size>{body}</annotation>", encoding="utf-8")


def test_groups_keep_consecutive_frames_together_and_splits_are_deterministic():
    assert yd.rdd_group("India_000101") == yd.rdd_group("India_000199") != yd.rdd_group("India_000250")
    assert yd.rdd_group("China_Drone_000008") == "China_Drone_0" and yd.rdd_group("India_000101") != yd.rdd_group("Japan_000101")
    assert yd.bharat_group("20250501091922_0060_frame_00021_jpg.rf.aaa") == yd.bharat_group("20250501091922_0060_frame_00064_jpg.rf.bbb") == "bph:20250501091922_0060"
    s = [yd.split_of(f"g{i}") for i in range(2000)]
    assert s == [yd.split_of(f"g{i}") for i in range(2000)]
    assert 0.75 < s.count("train") / 2000 < 0.85 and 0.07 < s.count("val") / 2000 < 0.13 and 0.07 < s.count("test") / 2000 < 0.13


def test_voc_to_yolo_normalises_clips_and_counts_what_it_skips():
    lines, st = yd.voc_boxes_to_yolo([{"name": "D40", "box": [64, 48, 192, 144]}, {"name": "D99", "box": [1, 1, 5, 5]}, {"name": "D00", "box": [10, 10, 10, 30]},
                                      {"name": "D10", "box": [-20, 0, 100, 960]}], W, H)
    assert lines[0] == "3 0.200000 0.200000 0.200000 0.200000"
    assert lines[1].startswith("1 0.078125 0.5") and st == {"boxes": 2, "unknown_class": 1, "degenerate": 1}


def synthetic_pairs(mapping, n_per_class=300, noise=0.0, seed=0):
    """VOC + YOLO boxes of the same invented images; YOLO ids follow ``mapping`` (id -> class name)."""
    rng, pairs = random.Random(seed), []
    for cid, name in mapping.items():
        for _ in range(n_per_class):
            x0, y0 = rng.uniform(0, 400), rng.uniform(0, 300)
            w, h = rng.uniform(30, 200), rng.uniform(30, 150)
            voc = [{"name": name, "box": [x0, y0, x0 + w, y0 + h]}]
            shown = cid if rng.random() >= noise else rng.choice([k for k in mapping if k != cid])
            yolo = [(shown, (x0 + w / 2) / W, (y0 + h / 2) / H, w / W, h / H)]
            pairs += yd.match_voc_to_yolo(voc, yolo, W, H)
    return pairs


def test_numeric_ids_are_decoded_only_from_evidence():
    truth = {0: "D40", 1: "D00", 2: "D10", 3: "D20"}
    d = yd.decode_class_ids(synthetic_pairs(truth))
    assert d["ok"] and d["mapping"] == truth and all(v["purity"] == 1.0 for v in d["per_id"].values())
    noisy = yd.decode_class_ids(synthetic_pairs(truth, noise=0.3))
    assert not noisy["ok"] and noisy["mapping"] == {}                                   # 70% purity: refuse, do not assume
    few = yd.decode_class_ids(synthetic_pairs(truth, n_per_class=20))
    assert not few["ok"]                                                              # too little evidence
    assert not yd.decode_class_ids([])["ok"]
    twice = yd.decode_class_ids(synthetic_pairs({0: "D40", 1: "D40", 2: "D00"}))      # two ids -> one class is a red flag
    assert not twice["ok"]


def test_collect_and_assemble_end_to_end_with_dedup_and_group_safe_splits(tmp_path):
    r20, r22, bph = tmp_path / "rdd2020", tmp_path / "rdd2022", tmp_path / "bph"
    stems = [f"India_{i:06d}" for i in range(0, 600, 3)]                              # 200 frames over 6 blocks of 100
    for s in stems:
        write_img(r20 / "train/India/images" / f"{s}.jpg")
        write_voc(r20 / "train/India/annotations/xmls" / f"{s}.xml", s, [("D40", (64, 48, 192, 144))])
    write_img(r20 / "train/Japan/images/Japan_000001.jpg")                            # filtered out by countries=["India"]
    write_voc(r20 / "train/Japan/annotations/xmls/Japan_000001.xml", "Japan_000001", [("D00", (1, 1, 50, 50))])
    for s in stems[:50] + ["China_Drone_000008"]:                                     # RDD2022 copy: 50 duplicates of RDD2020 stems + one new image; ids 0..3 unknown names
        write_img(r22 / "RDD_SPLIT/train/images" / f"{s}.jpg")
        (r22 / "RDD_SPLIT/train/labels").mkdir(parents=True, exist_ok=True)
        (r22 / "RDD_SPLIT/train/labels" / f"{s}.txt").write_text("0 0.2 0.2 0.2 0.2\n", encoding="utf-8")
    for i in range(30):
        s = f"20250501091922_{i // 10:04d}_frame_{i:05d}_jpg.rf.h{i}"
        write_img(bph / "train/images" / f"{s}.jpg")
        (bph / "train/labels").mkdir(parents=True, exist_ok=True)
        (bph / "train/labels" / f"{s}.txt").write_text("0 0.5 0.5 0.1 0.1\n", encoding="utf-8")
    (bph / "data.yaml").write_text("names: [pothole]\n", encoding="utf-8")            # not an image/label: must be ignored

    a, sa = yd.collect_rdd_voc(r20, countries=["India"])
    b, sb = yd.collect_yolo(r22, {0: "D40"}, source="rdd2022", group_fn=yd.rdd_group)
    c, sc = yd.collect_yolo(bph, {0: "D40"}, source="bharatpothole", group_fn=yd.bharat_group)
    assert sa["images"] == 200 and sa["boxes"] == 200 and sb["images"] == 51 and sc["images"] == 30
    out = tmp_path / "ds"
    m = yd.assemble(out, a + b + c, seed=1)
    assert m["duplicate_stems_dropped"] == 50 and m["images"] == 200 + 1 + 30 and m["groups_straddling_splits"] == 0
    assert set(m["split_counts"]) <= {"train", "val", "test"} and sum(m["split_counts"].values()) == m["images"]
    for sp in m["split_counts"]:                                                      # every image has a label file and a working symlink
        imgs = sorted((out / "images" / sp).iterdir())
        assert imgs and all(p.is_symlink() and p.resolve().exists() for p in imgs)
        assert {p.stem for p in imgs} == {p.stem for p in (out / "labels" / sp).iterdir()}
    assert "3: D40" in (out / "data.yaml").read_text() and m["boxes_per_class_by_split"]
    assert all(set(v) <= {"D40"} for v in m["boxes_per_class_by_split"].values())


def test_decode_from_overlap_names_the_ids_of_a_yolo_copy_by_matching_a_voc_copy(tmp_path):
    truth = {0: "D40", 1: "D00", 2: "D10", 3: "D20"}                                  # the (invented) id order of this YOLO copy
    rng = random.Random(3)
    voc_root, yolo_root = tmp_path / "voc", tmp_path / "yolo"
    stems = []
    for i in range(240):
        s = f"India_{i:06d}"
        stems.append(s)
        write_img(voc_root / "images" / f"{s}.jpg")
        write_img(yolo_root / "images" / f"{s}.jpg")
        cid = i % 4
        x0, y0, w, h = rng.uniform(0, 300), rng.uniform(0, 200), rng.uniform(40, 200), rng.uniform(40, 150)
        write_voc(voc_root / "xml" / f"{s}.xml", s, [(truth[cid], (x0, y0, x0 + w, y0 + h))])
        (yolo_root / "labels").mkdir(parents=True, exist_ok=True)
        (yolo_root / "labels" / f"{s}.txt").write_text(f"{cid} {(x0 + w / 2) / W} {(y0 + h / 2) / H} {w / W} {h / H}\n", encoding="utf-8")
    items, _ = yd.collect_rdd_voc(voc_root)
    res = yd.decode_from_overlap(items, yolo_root, min_pairs=50)
    assert res["ok"] and res["mapping"] == truth and res["overlapping_images"] == 240
    assert not yd.decode_from_overlap(items, tmp_path / "empty", min_pairs=50)["ok"]            # no overlap -> nothing may be assumed
