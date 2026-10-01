"""Pre-flight profile of an externally stored image dataset: what is actually there, BEFORE choosing a format.

Reports facts (file extensions, annotation artefacts, class-name files, videos, group structure) and *candidate*
formats; it never decides. Counts and relative paths only — no image content is read.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from .errors import SchemaMismatch

IMG = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO = {".mp4", ".avi", ".mov", ".mkv", ".mpg", ".mpeg", ".wmv"}
ARCHIVES = {".zip", ".tar", ".gz", ".tgz", ".7z", ".rar"}
CLASS_FILES = {"classes.txt", "obj.names", "data.yaml", "data.yml", "labels.txt", "classes.json", "names.txt", "class_names.txt", "classes.names"}
SPLIT_WORDS = {"train": "train", "training": "train", "val": "val", "valid": "val", "validation": "val", "test": "test", "testing": "test", "test1": "test", "test2": "test"}
COUNTRY_WORDS = ("india", "japan", "czech", "norway", "united_states", "unitedstates", "usa", "china", "motorbike", "drone")


def directory_tree(root: Path, depth: int = 3, max_entries: int = 80) -> list[dict]:
    """Directory outline (relative names, file counts per extension) so the operator SEES the real layout. Names/counts only."""
    out: list[dict] = []
    root = Path(root)

    def walk(d: Path, level: int) -> None:
        if len(out) >= max_entries:
            return
        files: Counter = Counter()
        subs = []
        for p in sorted(d.iterdir()):
            if p.is_dir():
                subs.append(p)
            else:
                files[p.suffix.lower() or "(none)"] += 1
        out.append({"dir": str(d.relative_to(root)) or ".", "files_by_extension": dict(files.most_common(6)), "subdirectories": len(subs)})
        if level < depth:
            for sd in subs:
                walk(sd, level + 1)

    walk(root, 0)
    return out


def _class_file_preview(path: Path) -> dict:
    from .adapters.detection import load_class_names  # local import: adapters import this module's constants
    try:
        names = load_class_names(path)
        return {"file": str(path), "n_classes": len(names), "names_first_30": names[:30]}
    except Exception as e:    # noqa: BLE001  (a preview failure must never stop profiling)
        return {"file": str(path), "unreadable": f"{type(e).__name__}: {e}"}


def _looks_voc(path: Path) -> bool:
    try:
        raw = path.read_bytes()[:200_000]
        if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
            return False
        return b"<annotation" in raw and (b"<object" in raw or b"<size" in raw or b"<filename" in raw)
    except OSError:
        return False


_YOLO_LINE = re.compile(r"^\d+(\s+-?\d*\.?\d+){4,}\s*$")


def _looks_yolo(path: Path) -> bool:
    try:
        lines = [ln for ln in path.read_text(encoding="utf-8", errors="ignore").splitlines()[:20] if ln.strip()]
    except OSError:
        return False
    return bool(lines) and all(_YOLO_LINE.match(ln.strip()) for ln in lines)


def profile_image_dataset(root: Path, *, sample: int = 12) -> dict:
    """Facts about what is actually under ``root`` (nothing assumed): extensions, directory outline, image counts, annotation artefacts with
    content sniffing (VOC / YOLO / COCO), class-name files with their contents, splits and country markers found in path components, archives,
    videos, group structure, same-stem annotation coverage, and a SUGGESTED (never applied) configuration."""
    root = Path(root)
    if not root.is_dir():
        raise SchemaMismatch(f"dataset root not found: {root}")
    ext: Counter = Counter()
    top: Counter = Counter()
    parents: Counter = Counter()
    split_images: Counter = Counter()
    country_images: Counter = Counter()
    images, xmls, txts, jsons, videos, class_files, archives = [], [], [], [], [], [], []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        e = p.suffix.lower()
        ext[e or "(none)"] += 1
        rel = p.relative_to(root)
        top[rel.parts[0] if len(rel.parts) > 1 else "."] += 1
        if p.name.lower() in CLASS_FILES:
            class_files.append(rel)
        elif e in IMG:
            images.append(rel)
            parents[str(rel.parent)] += 1
            low = [x.lower() for x in rel.parts[:-1]]
            for w in low:
                if w in SPLIT_WORDS:
                    split_images[SPLIT_WORDS[w]] += 1
                    break
            for w in low:
                hit = next((c for c in COUNTRY_WORDS if c in w), None)
                if hit:
                    country_images[hit] += 1
                    break
        elif e == ".xml":
            xmls.append(p)
        elif e == ".txt":
            txts.append(p)
        elif e == ".json":
            jsons.append(p)
        elif e in VIDEO:
            videos.append(rel)
        elif e in ARCHIVES:
            archives.append(str(rel))
    coco = []
    for p in jsons[:20]:
        try:
            if p.stat().st_size < 50_000_000:
                d = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(d, dict) and {"images", "annotations", "categories"} <= set(d):
                    coco.append(str(p.relative_to(root)))
        except (OSError, ValueError):
            pass
    voc_files = [p for p in xmls[:5] if _looks_voc(p)]
    yolo_files = [p for p in txts[:40] if _looks_yolo(p)]
    voc_like, yolo_like = bool(voc_files), bool(yolo_files)
    candidates = [f for f, ok in (("voc", voc_like), ("yolo", yolo_like), ("coco", bool(coco)), ("folder", len(parents) >= 2)) if ok]
    img_stems = Counter(r.stem for r in images)
    ann_stems = {p.stem for p in xmls} | {p.stem for p in txts}
    covered = sum(c for st, c in img_stems.items() if st in ann_stems)
    names = [r.stem for r in images[:2000]]
    numbered = sum(bool(re.search(r"\d+$", n)) for n in names)
    previews = [_class_file_preview(root / r) for r in class_files[:5]]
    warnings = []
    if "yolo" in candidates and not class_files:
        warnings.append("YOLO-style labels but NO class-names file found: class ids cannot be named; obtain the dataset's own class list (never guess).")
    if videos:
        warnings.append(f"{len(videos)} video file(s): frames must be extracted externally (e.g. ffmpeg) keeping the video id in the file/dir name, so splits can hold out whole videos.")
    if archives:
        warnings.append(f"{len(archives)} archive file(s) {archives[:3]} inside the input: Kaggle did not extract them and this notebook never copies data; use a copy that is already extracted.")
    if not candidates:
        warnings.append("no annotation format recognised; the images may be unlabelled")
    if len(candidates) > 1:
        warnings.append(f"several annotation formats look present {candidates}: choose one explicitly.")
    if images and ann_stems and covered < len(images):
        warnings.append(f"only {covered}/{len(images)} images have a same-stem annotation file: the rest are UNANNOTATED, not negatives.")
    if len(parents) <= 1 and not numbered:
        warnings.append("no directory or filename structure usable as a group id: random frame splits would leak")
    if len(country_images) > 1:
        warnings.append(f"several country markers in the paths {dict(country_images)}: set an explicit `countries` filter for a country subset.")
    if split_images:
        warnings.append(f"split-like directories found {dict(split_images)}: source splits are NOT used unless you opt in (`split_from_path`), and may themselves leak near-identical frames.")
    suggested: dict = {}
    ann_formats = [c for c in candidates if c != "folder"]          # "folder" (labels from directory names) is only a fallback candidate
    if len(ann_formats) == 1:
        suggested["format"] = ann_formats[0]
    elif candidates:
        suggested["format"] = f"one of {candidates}"
    if previews and len([c for c in class_files]) == 1:
        suggested["class_names_file"] = str(class_files[0])
    return {"root_name": root.name, "n_images": len(images), "extensions": dict(ext.most_common()), "top_level_entries": dict(top.most_common(20)),
            "directory_outline": directory_tree(root), "n_image_directories": len(parents), "largest_image_directories": parents.most_common(10),
            "annotation_artifacts": {"xml": len(xmls), "txt": len(txts), "json": len(jsons)},
            "annotation_content_sniffed": {"voc_xml_like_of_first_5": len(voc_files), "yolo_txt_like_of_first_40": len(yolo_files)},
            "coco_style_json": coco, "class_name_files": [str(r) for r in class_files], "class_name_previews": previews,
            "split_directories_images": dict(split_images), "country_markers_images": dict(country_images), "archives": archives[:20],
            "videos": [str(v) for v in videos[:20]], "n_videos": len(videos), "numbered_filename_share": round(numbered / max(len(names), 1), 3),
            "images_with_same_stem_annotation": covered, "images_without_same_stem_annotation": len(images) - covered,
            "duplicate_image_stems": sum(1 for c in img_stems.values() if c > 1), "sample_relative_paths": [str(r) for r in images[:sample]],
            "format_candidates": candidates, "suggested_config_NOT_APPLIED": suggested, "warnings": warnings,
            "note": "Candidates and suggestions are NOT decisions: set IMAGE[...] yourself after reading this profile; nothing is guessed or applied automatically."}
