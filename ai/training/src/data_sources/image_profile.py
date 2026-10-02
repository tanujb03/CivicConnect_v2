"""Pre-flight profile of an externally stored image dataset: what is actually there, BEFORE choosing a format.

Reports facts (file extensions, annotation artefacts, class-name files, videos, group structure) and *candidate*
formats; it never decides. Counts and relative paths only — no image content is read.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path, PurePosixPath

from .errors import SchemaMismatch

IMG = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO = {".mp4", ".avi", ".mov", ".mkv", ".mpg", ".mpeg", ".wmv"}
ARCHIVES = {".zip", ".tar", ".gz", ".tgz", ".7z", ".rar"}
CLASS_FILES = {"classes.txt", "obj.names", "data.yaml", "data.yml", "labels.txt", "classes.json", "names.txt", "class_names.txt", "classes.names"}
SPLIT_WORDS = {"train": "train", "training": "train", "val": "val", "valid": "val", "validation": "val", "test": "test", "testing": "test", "test1": "test", "test2": "test"}
COUNTRY_WORDS = ("india", "japan", "czech", "norway", "united_states", "unitedstates", "usa", "china", "motorbike", "drone")


def directory_tree(root: Path, depth: int = 3, max_entries: int = 80) -> list[dict]:
    """Directory outline of a real tree (names, file counts per extension)."""
    root = Path(root)
    return outline_from_entries([(str(p.relative_to(root)), 0) for p in sorted(root.rglob("*")) if p.is_file()], depth, max_entries)


def outline_from_entries(entries: list[tuple[str, int]], depth: int = 3, max_entries: int = 80) -> list[dict]:
    """Directory outline from (relative path, size) pairs — works for a filesystem walk or an archive listing alike."""
    dirs: dict[str, Counter] = {}
    children: dict[str, set] = {}
    for rel, _ in entries:
        parts = PurePosixPath(rel).parts
        for lvl in range(0, min(len(parts) - 1, depth) + 1):
            d = "/".join(parts[:lvl]) or "."
            dirs.setdefault(d, Counter())
            if lvl + 1 < len(parts):
                children.setdefault(d, set()).add(parts[lvl])
        d = "/".join(parts[:-1][:depth + 1]) or "."
        if len(parts) - 1 <= depth:
            dirs[d][PurePosixPath(rel).suffix.lower() or "(none)"] += 1
    ordered = sorted(dirs, key=lambda x: (x.count("/") if x != "." else -1, x))
    return [{"dir": d, "files_by_extension": dict(dirs[d].most_common(6)), "subdirectories": len(children.get(d, ()))} for d in ordered[:max_entries]]


def _class_preview_from_text(name: str, text: str) -> dict:
    from .adapters.detection import parse_class_names  # local import: adapters import this module's constants
    try:
        names = parse_class_names(text, PurePosixPath(name).suffix.lower(), name)
        return {"file": name, "n_classes": len(names), "names_first_30": names[:30]}
    except Exception as e:    # noqa: BLE001  (a preview failure must never stop profiling)
        return {"file": name, "unreadable": f"{type(e).__name__}: {e}"}


def _looks_voc(raw: bytes) -> bool:
    raw = raw[:200_000]
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        return False
    return b"<annotation" in raw and (b"<object" in raw or b"<size" in raw or b"<filename" in raw)


_YOLO_LINE = re.compile(r"^\d+(\s+-?\d*\.?\d+){4,}\s*$")


def _looks_yolo(raw: bytes) -> bool:
    lines = [ln for ln in raw[:20_000].decode("utf-8", errors="ignore").splitlines()[:20] if ln.strip()]
    return bool(lines) and all(_YOLO_LINE.match(ln.strip()) for ln in lines)


def _yolo_class_id_histogram(txts: list[str], read, max_files: int = 2000) -> dict:
    """Facts for a dataset whose YOLO labels carry numeric class ids but no class-names file: WHICH ids occur and how often (evenly spaced sample of the
    label files). It does not say what the ids mean: the names must come from the dataset's own documentation."""
    step = max(1, len(txts) // max_files)
    ids: Counter = Counter()
    sampled = 0
    for rel in txts[::step][:max_files]:
        sampled += 1
        for line in read(rel, 20_000).decode("utf-8", errors="ignore").splitlines():
            tok = line.split(None, 1)[0] if line.strip() else ""
            if tok.lstrip("-").isdigit():
                ids[int(tok)] += 1
    return {"label_files_sampled": sampled, "label_files_total": len(txts), "class_id_counts": dict(sorted(ids.items())),
            "note": "ids only: the meaning of each id must come from the dataset's own class list; it is never guessed."}


def profile_image_dataset(root: Path, *, sample: int = 12) -> dict:
    """Facts about what is actually under ``root`` (a real directory tree). See :func:`profile_entries`."""
    root = Path(root)
    if not root.is_dir():
        raise SchemaMismatch(f"dataset root not found: {root}")
    entries = [(str(p.relative_to(root)), p.stat().st_size) for p in sorted(root.rglob("*")) if p.is_file()]

    def read(rel: str, n: int = 200_000) -> bytes:
        try:
            with open(root / rel, "rb") as f:
                return f.read(n)
        except OSError:
            return b""
    out = profile_entries(entries, read, root.name)
    out["source"] = "directory"
    return out


def profile_archive(archive: Path, *, sample: int = 12) -> dict:
    """The same profile computed from an archive's member listing and a few in-memory member reads. NOTHING is extracted."""
    from .archive_tools import ArchiveReader
    r = ArchiveReader(archive)
    try:
        entries = r.entries()
        out = profile_entries(entries, lambda rel, n=200_000: r.read(rel, n), Path(archive).name)
    finally:
        r.close()
    out["source"] = f"archive ({r.kind}), listing only — not extracted"
    return out


def profile_entries(entries: list[tuple[str, int]], read, root_name: str, *, sample: int = 12) -> dict:
    """Facts only (nothing assumed): extensions, directory outline, image counts, annotation artefacts with content sniffing (VOC / YOLO / COCO),
    class-name files with their contents, splits and country markers in path components, archives, videos, group structure, same-stem
    annotation coverage, and a SUGGESTED (never applied) configuration."""
    ext: Counter = Counter()
    top: Counter = Counter()
    parents: Counter = Counter()
    split_images: Counter = Counter()
    country_images: Counter = Counter()
    country_in_names: Counter = Counter()
    images, xmls, txts, jsons, videos, class_files, archives = [], [], [], [], [], [], []
    for rel, size in entries:
        pp = PurePosixPath(rel)
        e = pp.suffix.lower()
        ext[e or "(none)"] += 1
        top[pp.parts[0] if len(pp.parts) > 1 else "."] += 1
        if pp.name.lower() in CLASS_FILES:
            class_files.append(rel)
        elif e in IMG:
            images.append(rel)
            parents[str(pp.parent)] += 1
            low = [x.lower() for x in pp.parts[:-1]]
            for w in low:
                if w in SPLIT_WORDS:
                    split_images[SPLIT_WORDS[w]] += 1
                    break
            for w in low:
                hit = next((c for c in COUNTRY_WORDS if c in w), None)
                if hit:
                    country_images[hit] += 1
                    break
            else:   # no country in the directories: some re-uploads encode it in the file name instead (e.g. India_000123.jpg, China_Drone_000008.jpg)
                hit = next((c for c in COUNTRY_WORDS if c in pp.stem.lower()), None)
                if hit:
                    country_in_names[hit] += 1
        elif e == ".xml":
            xmls.append(rel)
        elif e == ".txt":
            txts.append(rel)
        elif e == ".json":
            jsons.append((rel, size))
        elif e in VIDEO:
            videos.append(rel)
        elif e in ARCHIVES:
            archives.append(rel)
    coco = []
    for rel, size in jsons[:20]:
        try:
            if size < 50_000_000:
                d = json.loads(read(rel, 50_000_000).decode("utf-8"))
                if isinstance(d, dict) and {"images", "annotations", "categories"} <= set(d):
                    coco.append(rel)
        except (ValueError, UnicodeDecodeError):
            pass
    voc_files = [x for x in xmls[:5] if _looks_voc(read(x))]
    yolo_files = [x for x in txts[:40] if _looks_yolo(read(x))]
    voc_like, yolo_like = bool(voc_files), bool(yolo_files)
    yolo_ids = _yolo_class_id_histogram(txts, read) if yolo_like else None
    candidates = [f for f, ok in (("voc", voc_like), ("yolo", yolo_like), ("coco", bool(coco)), ("folder", len(parents) >= 2)) if ok]
    img_stems = Counter(PurePosixPath(r).stem for r in images)
    ann_stems = {PurePosixPath(p).stem for p in xmls} | {PurePosixPath(p).stem for p in txts}
    covered = sum(c for st, c in img_stems.items() if st in ann_stems)
    names = [PurePosixPath(r).stem for r in images[:2000]]
    numbered = sum(bool(re.search(r"\d+$", n)) for n in names)
    previews = [_class_preview_from_text(r, read(r, 200_000).decode("utf-8", errors="ignore")) for r in class_files[:5]]
    warnings = []
    if "yolo" in candidates and not class_files:
        warnings.append("YOLO-style labels but NO class-names file found: class ids cannot be named; obtain the dataset's own class list (never guess).")
    if videos:
        warnings.append(f"{len(videos)} video file(s): frames must be extracted externally (e.g. ffmpeg) keeping the video id in the file/dir name, so splits can hold out whole videos.")
    if archives:
        warnings.append(f"{len(archives)} archive file(s) {archives[:3]} inside the input: this notebook never unpacks nested archives; use an extracted copy.")
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
    if previews and len(class_files) == 1:
        suggested["class_names_file"] = class_files[0]
    return {"root_name": root_name, "n_images": len(images), "extensions": dict(ext.most_common()), "top_level_entries": dict(top.most_common(20)),
            "directory_outline": outline_from_entries(entries), "n_image_directories": len(parents), "largest_image_directories": parents.most_common(10),
            "annotation_artifacts": {"xml": len(xmls), "txt": len(txts), "json": len(jsons)},
            "annotation_content_sniffed": {"voc_xml_like_of_first_5": len(voc_files), "yolo_txt_like_of_first_40": len(yolo_files)},
            "coco_style_json": coco, "class_name_files": class_files, "class_name_previews": previews,
            "yolo_class_id_histogram_sample": yolo_ids,
            "split_directories_images": dict(split_images), "country_markers_images": dict(country_images), "country_markers_in_filenames": dict(country_in_names),
            "archives": archives[:20],
            "videos": videos[:20], "n_videos": len(videos), "numbered_filename_share": round(numbered / max(len(names), 1), 3),
            "images_with_same_stem_annotation": covered, "images_without_same_stem_annotation": len(images) - covered,
            "duplicate_image_stems": sum(1 for c in img_stems.values() if c > 1), "sample_relative_paths": images[:sample],
            "format_candidates": candidates, "suggested_config_NOT_APPLIED": suggested, "warnings": warnings,
            "note": "Candidates and suggestions are NOT decisions: set IMAGE[...] yourself after reading this profile; nothing is guessed or applied automatically."}
