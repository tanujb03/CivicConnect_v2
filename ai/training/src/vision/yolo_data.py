"""Data preparation for the road-damage DETECTOR (notebook 06): pure functions, unit-tested offline.

Design rules (same as the rest of the data framework): nothing is guessed, splits are group-safe, and every decision is reported.
  * RDD classes are the four named classes D00 / D10 / D20 / D40 (VOC files carry the names). A YOLO copy that ships only numeric ids is DECODED by
    matching its boxes against a VOC copy of the same images and measuring agreement; if agreement is not near-perfect the ids stay unusable.
  * Splits are by GROUP (country + index block for RDD frames, source video for BharatPotHole). The sources' own train/val/test folders are ignored:
    re-uploads split frame-by-frame, which leaks near-identical consecutive frames across splits.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
from collections import Counter, defaultdict
from typing import Iterable, Sequence

from ai.training.src.data_sources.splits import hash_fraction

log = logging.getLogger(__name__)

CLASSES = ["D00", "D10", "D20", "D40"]          # longitudinal crack, transverse crack, alligator crack, pothole
CLASS_MEANING = {"D00": "longitudinal crack", "D10": "transverse crack", "D20": "alligator crack", "D40": "pothole"}
CIVIC_MAPPING = {"D40": ("roads", "pothole"), "D00": ("roads", None), "D10": ("roads", None), "D20": ("roads", None)}
_TRAILING = re.compile(r"(\d+)$")
_BHARAT = re.compile(r"^(.+?)(?:_frame_\d+)?_jpg\.rf\.")


def rdd_group(stem: str, block: int = 100) -> str:
    """'India_000123' -> 'India_1' ; 'China_Drone_000008' -> 'China_Drone_0' (consecutive frames are usually one drive, so whole blocks stay together)."""
    m = _TRAILING.search(stem)
    prefix = stem[: m.start()].rstrip("_") if m else stem
    return f"{prefix}_{int(m.group(1)) // block}" if m else f"{prefix}_nogroup"


def bharat_group(stem: str) -> str:
    m = _BHARAT.search(stem)
    return f"bph:{m.group(1)}" if m else f"bph:{stem}"


def split_of(group: str, seed: int = 42, val: float = 0.1, test: float = 0.1) -> str:
    """Deterministic group split: the same group is always on the same side."""
    f = hash_fraction(group, seed)
    return "test" if f < test else "val" if f < test + val else "train"


def voc_boxes_to_yolo(objs: Sequence[dict], width: int, height: int, classes: Sequence[str] = CLASSES) -> tuple[list[str], dict]:
    """VOC objects ([{'name','box':[xmin,ymin,xmax,ymax]}]) -> YOLO label lines; unknown class names and degenerate boxes are skipped and counted."""
    lines, stats = [], Counter()
    idx = {c: i for i, c in enumerate(classes)}
    for o in objs:
        x0, y0, x1, y1 = o["box"]
        if o["name"] not in idx:
            stats["unknown_class"] += 1
            continue
        if not (x1 > x0 and y1 > y0) or width <= 0 or height <= 0:
            stats["degenerate"] += 1
            continue
        x0, x1 = max(0.0, x0), min(float(width), x1)
        y0, y1 = max(0.0, y0), min(float(height), y1)
        lines.append(f"{idx[o['name']]} {(x0 + x1) / 2 / width:.6f} {(y0 + y1) / 2 / height:.6f} {(x1 - x0) / width:.6f} {(y1 - y0) / height:.6f}")
        stats["boxes"] += 1
    return lines, dict(stats)


def parse_yolo_lines(text: str) -> list[tuple[int, float, float, float, float]]:
    out = []
    for line in text.splitlines():
        f = line.split()
        if len(f) >= 5:
            try:
                out.append((int(float(f[0])), *map(float, f[1:5])))
            except ValueError:
                continue
    return out


def _iou(a: Sequence[float], b: Sequence[float]) -> float:
    ix0, iy0, ix1, iy1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def match_voc_to_yolo(voc_objs: Sequence[dict], yolo_boxes: Sequence[tuple], width: int, height: int, iou_min: float = 0.6) -> list[tuple[int, str]]:
    """Greedy one-to-one box matching between a VOC annotation and a YOLO annotation of the SAME image -> [(yolo_id, voc_class_name)]."""
    ys = [(cid, [(cx - w / 2) * width, (cy - h / 2) * height, (cx + w / 2) * width, (cy + h / 2) * height]) for cid, cx, cy, w, h in yolo_boxes]
    pairs, used = [], set()
    for o in voc_objs:
        best, bj = 0.0, -1
        for j, (_cid, box) in enumerate(ys):
            if j in used:
                continue
            v = _iou(o["box"], box)
            if v > best:
                best, bj = v, j
        if bj >= 0 and best >= iou_min:
            used.add(bj)
            pairs.append((ys[bj][0], o["name"]))
    return pairs


def decode_class_ids(pairs: Iterable[tuple[int, str]], *, min_pairs: int = 200, min_purity: float = 0.97) -> dict:
    """Which class NAME does each YOLO id stand for? Evidence = matched boxes between two copies of the same images. Returns the decoded mapping only when
    every id has enough matches and one name explains at least ``min_purity`` of them; otherwise ``ok`` is False and nothing may be assumed."""
    table: dict[int, Counter] = defaultdict(Counter)
    for cid, name in pairs:
        table[cid][name] += 1
    mapping, report, ok = {}, {}, bool(table)
    for cid, c in sorted(table.items()):
        n = sum(c.values())
        name, k = c.most_common(1)[0]
        purity = k / n
        report[cid] = {"matched_boxes": n, "names": dict(c), "best_name": name, "purity": round(purity, 4)}
        if n >= min_pairs and purity >= min_purity:
            mapping[cid] = name
        else:
            ok = False
    names = list(mapping.values())
    if len(set(names)) != len(names):          # two ids decoding to the same class is a sign of a bad match, not a result
        ok = False
    return {"ok": ok, "mapping": mapping if ok else {}, "per_id": report, "min_pairs": min_pairs, "min_purity": min_purity}


def class_counts(label_texts: Iterable[str], n_classes: int = len(CLASSES)) -> dict[str, int]:
    c: Counter = Counter()
    for t in label_texts:
        for cid, *_ in parse_yolo_lines(t):
            if 0 <= cid < n_classes:
                c[CLASSES[cid]] += 1
    return dict(c)


# ----------------------------------------------------------------------------------------------- collecting + assembling (touches files; read-only on sources)
IMG_EXT = {".jpg", ".jpeg", ".png"}


def _index_images(root, countries: Sequence[str] | None = None) -> dict:
    from pathlib import Path
    out = {}
    for p in sorted(Path(root).rglob("*")):
        if p.is_file() and p.suffix.lower() in IMG_EXT:
            if countries and not any(c.lower() in "/".join(p.parts).lower() for c in countries):
                continue
            out.setdefault(p.stem, p)
    return out


def collect_rdd_voc(root, countries: Sequence[str] | None = None, source: str = "rdd2020") -> tuple[list[dict], dict]:
    """VOC copy (class NAMES in the xml). Only annotated images are returned; images without an xml are not negatives and are ignored."""
    from pathlib import Path

    from ai.training.src.data_sources.adapters.rdd2022 import parse_voc
    from ai.training.src.data_sources.errors import SchemaMismatch
    imgs = _index_images(root, countries)
    items, stats = [], Counter()
    for x in sorted(Path(root).rglob("*.xml")):
        img = imgs.get(x.stem)
        if img is None:
            stats["xml_without_image"] += 1
            continue
        try:
            a = parse_voc(x)
        except SchemaMismatch:
            stats["invalid_xml"] += 1
            continue
        if not (a["width"] and a["height"]):
            stats["no_size"] += 1
            continue
        lines, st = voc_boxes_to_yolo(a["objects"], a["width"], a["height"])
        stats.update(st)
        items.append({"source": source, "stem": x.stem, "image": img, "label_lines": lines, "group": rdd_group(x.stem), "voc": a["objects"], "size": (a["width"], a["height"])})
    stats["images"] = len(items)
    return items, dict(stats)


def collect_yolo(root, id_to_class: dict[int, str], *, source: str, group_fn, countries: Sequence[str] | None = None) -> tuple[list[dict], dict]:
    """YOLO copy with a KNOWN id -> class-name mapping (from a class-names file or from ``decode_class_ids``). Ids outside the mapping are dropped and counted."""
    from pathlib import Path
    imgs = _index_images(root, countries)
    labels = {p.stem: p for p in sorted(Path(root).rglob("*.txt")) if p.name.lower() not in ("classes.txt", "labels.txt")}
    idx = {c: i for i, c in enumerate(CLASSES)}
    items, stats = [], Counter()
    for stem, img in imgs.items():
        lab = labels.get(stem)
        if lab is None:
            stats["image_without_label_file"] += 1
            continue
        raw = parse_yolo_lines(lab.read_text(encoding="utf-8", errors="ignore"))
        lines = []
        for cid, cx, cy, w, h in raw:
            name = id_to_class.get(cid)
            if name not in idx:
                stats["dropped_unmapped_id"] += 1
                continue
            lines.append(f"{idx[name]} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
        items.append({"source": source, "stem": stem, "image": img, "label_lines": lines, "group": group_fn(stem), "yolo": raw})
    stats["images"] = len(items)
    return items, dict(stats)


def link_or_copy(src, dst) -> str:
    """Make ``dst`` an image of ``src`` and return the method used: ``symlink`` (Linux/Kaggle, and Windows with Developer Mode), else ``hardlink`` (same volume),
    else ``copy``. Windows without the symlink privilege raises WinError 1314; read-only inputs on another volume cannot be hardlinked."""
    for method, make in (("symlink", os.symlink), ("hardlink", os.link), ("copy", shutil.copyfile)):
        try:
            make(src, dst)
            return method
        except OSError as exc:
            if method == "copy":
                raise
            log.debug("%s %s -> %s failed (%s); trying the next method", method, src, dst, exc)
    raise AssertionError("unreachable")  # pragma: no cover


def assemble(out, items: Sequence[dict], *, seed: int = 42, val: float = 0.1, test: float = 0.1) -> dict:
    """Write an Ultralytics dataset under ``out`` (images are SYMLINKS to the read-only inputs, or hardlinks/copies where symlinks are not allowed, see
    ``link_or_copy``; labels are written). Duplicated stems across sources (RDD2020 is contained in RDD2022) keep the FIRST item and are counted. Empty label
    files are kept (background images). Returns a manifest with counts per split/source/class."""
    from pathlib import Path
    out = Path(out)
    methods: Counter = Counter()
    seen, kept, dup = set(), [], 0
    for it in items:
        key = it["stem"] if it["source"].startswith("rdd") else f"{it['source']}:{it['stem']}"
        if key in seen:
            dup += 1
            continue
        seen.add(key)
        kept.append(it)
    split_counts: Counter = Counter()
    by_source: dict[str, Counter] = defaultdict(Counter)
    class_by_split: dict[str, Counter] = defaultdict(Counter)
    groups: dict[str, set] = defaultdict(set)
    for it in kept:
        sp = split_of(it["group"], seed, val, test)
        groups[it["group"]].add(sp)
        for d in ("images", "labels"):
            (out / d / sp).mkdir(parents=True, exist_ok=True)
        name = f"{it['source']}__{it['stem']}"
        link = out / "images" / sp / f"{name}{Path(it['image']).suffix.lower()}"
        if not link.exists():
            methods[link_or_copy(Path(it["image"]).resolve(), link)] += 1
        (out / "labels" / sp / f"{name}.txt").write_text("\n".join(it["label_lines"]) + ("\n" if it["label_lines"] else ""), encoding="utf-8")
        split_counts[sp] += 1
        by_source[it["source"]][sp] += 1
        for ln in it["label_lines"]:
            class_by_split[sp][CLASSES[int(ln.split()[0])]] += 1
    if methods:
        (log.info if set(methods) == {"symlink"} else log.warning)("assemble: images placed by %s", dict(methods))
    straddling = sum(1 for s in groups.values() if len(s) > 1)
    yaml = "path: " + str(out.resolve()) + "\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n" + "".join(f"  {i}: {c}\n" for i, c in enumerate(CLASSES))
    (out / "data.yaml").write_text(yaml, encoding="utf-8")
    return {"images": len(kept), "duplicate_stems_dropped": dup, "split_counts": dict(split_counts), "by_source": {k: dict(v) for k, v in by_source.items()},
            "boxes_per_class_by_split": {k: dict(v) for k, v in class_by_split.items()}, "n_groups": len(groups), "groups_straddling_splits": straddling,
            "classes": CLASSES, "seed": seed, "fractions": {"val": val, "test": test}}


def decode_from_overlap(voc_items: Sequence[dict], yolo_root, *, countries: Sequence[str] | None = None, min_pairs: int = 200, min_purity: float = 0.97) -> dict:
    """Decode a YOLO copy's numeric ids against a VOC copy of (some of) the same images: boxes of images present in BOTH are matched and the ids are named by
    agreement. ``voc_items`` come from ``collect_rdd_voc``. Reports how many images overlapped; refuses (ok=False) without strong agreement."""
    from pathlib import Path
    imgs = _index_images(yolo_root, countries)
    labels = {p.stem: p for p in sorted(Path(yolo_root).rglob("*.txt"))}
    pairs, overlap = [], 0
    for it in voc_items:
        lab = labels.get(it["stem"])
        if lab is None or it["stem"] not in imgs:
            continue
        overlap += 1
        w, h = it["size"]
        pairs += match_voc_to_yolo(it["voc"], parse_yolo_lines(lab.read_text(encoding="utf-8", errors="ignore")), w, h)
    res = decode_class_ids(pairs, min_pairs=min_pairs, min_purity=min_purity)
    res["overlapping_images"] = overlap
    res["matched_boxes"] = len(pairs)
    return res
