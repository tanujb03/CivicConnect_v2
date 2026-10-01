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
CLASS_FILES = {"classes.txt", "obj.names", "data.yaml", "data.yml", "labels.txt", "classes.json"}


def profile_image_dataset(root: Path, *, sample: int = 12) -> dict:
    root = Path(root)
    if not root.is_dir():
        raise SchemaMismatch(f"dataset root not found: {root}")
    ext: Counter = Counter()
    top: Counter = Counter()
    parents: Counter = Counter()
    images, xml, txt, jsons, videos, class_files = [], 0, 0, [], [], []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        e = p.suffix.lower()
        ext[e] += 1
        rel = p.relative_to(root)
        top[rel.parts[0] if len(rel.parts) > 1 else "."] += 1
        if e in IMG:
            images.append(rel)
            parents[str(rel.parent)] += 1
        elif e == ".xml":
            xml += 1
        elif e == ".txt":
            txt += 1
        elif e == ".json":
            jsons.append(p)
        elif e in VIDEO:
            videos.append(rel)
        if p.name.lower() in CLASS_FILES:
            class_files.append(str(rel))
    coco = []
    for p in jsons[:20]:
        try:
            if p.stat().st_size < 50_000_000:
                d = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(d, dict) and {"images", "annotations", "categories"} <= set(d):
                    coco.append(str(p.relative_to(root)))
        except (OSError, ValueError):
            pass
    voc_like = any(p.suffix.lower() == ".xml" for p in list(root.rglob("*.xml"))[:3]) and xml > 0
    yolo_like = txt > 0 and any((root / r).with_suffix(".txt").exists() or "labels" in {x.lower() for x in r.parts} for r in images[:50]) or any(
        "labels" in {x.lower() for x in p.relative_to(root).parts} for p in root.rglob("*.txt"))
    candidates = [f for f, ok in (("voc", voc_like), ("yolo", yolo_like), ("coco", bool(coco)), ("folder", len(parents) >= 2)) if ok]
    names = [r.stem for r in images[:2000]]
    numbered = sum(bool(re.search(r"\d+$", n)) for n in names)
    warnings = []
    if "yolo" in candidates and not class_files:
        warnings.append("YOLO-style labels but NO class-names file found: class ids cannot be named; obtain the dataset's own class list (never guess).")
    if videos:
        warnings.append(f"{len(videos)} video file(s): frames must be extracted externally (e.g. ffmpeg) keeping the video id in the file/dir name, so splits can hold out whole videos.")
    if not candidates:
        warnings.append("no annotation format recognised; the images may be unlabelled")
    if len(parents) <= 1 and not numbered:
        warnings.append("no directory or filename structure usable as a group id: random frame splits would leak")
    return {"root_name": root.name, "n_images": len(images), "extensions": dict(ext.most_common()), "top_level_entries": dict(top.most_common(20)),
            "n_image_directories": len(parents), "largest_image_directories": parents.most_common(10), "annotation_artifacts": {"xml": xml, "txt": txt, "json": len(jsons)},
            "coco_style_json": coco, "class_name_files": class_files, "videos": [str(v) for v in videos[:20]], "n_videos": len(videos),
            "numbered_filename_share": round(numbered / max(len(names), 1), 3), "sample_relative_paths": [str(r) for r in images[:sample]],
            "format_candidates": candidates, "warnings": warnings,
            "note": "Candidates are NOT decisions: choose --format yourself after inspecting samples; the adapter never guesses."}
