"""Aggregate audits of an externally stored image dataset (read in place, e.g. under /kaggle/input).

Everything returned is an aggregate (counts, distributions, a few example relative paths): no pixels, no per-image
rows. Pillow is optional: file formats/dimensions are read from the file headers by this module, and only the
near-duplicate (perceptual hash) check needs Pillow — without it the report says so instead of silently skipping.

Audits (each answers a leakage or validity question before any evaluation):
* image_files_audit  - formats (extension vs magic bytes), dimensions, file sizes, unreadable/missing files,
                       EXACT duplicates (sha1) and NEAR duplicates (64-bit difference hash, capped), and how many
                       duplicate pairs straddle groups / train-holdout (the leakage that matters).
* annotation_audit   - class distribution (raw and mapped), boxes per image, unannotated images, images with no
                       box (negatives?), box-size distribution when image sizes are known, mapping coverage.
* group_audit        - group (video/sequence/directory/block) sizes and whether any group straddles the split.
"""
from __future__ import annotations

import hashlib
import statistics
import struct
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, Iterable, Sequence

NEAR_HAMMING = 5            # <= this many differing bits of 64 => "near duplicate"
_MAGIC = ((b"\xff\xd8\xff", "jpeg"), (b"\x89PNG\r\n\x1a\n", "png"), (b"BM", "bmp"), (b"RIFF", "webp"), (b"GIF8", "gif"))


def sniff_format(head: bytes) -> str | None:
    return next((name for magic, name in _MAGIC if head.startswith(magic)), None)


def read_image_header(path: Path) -> dict:
    """{format, width, height} from the file header (None where unknown). Never decodes pixels."""
    try:
        with open(path, "rb") as f:
            head = f.read(32)
            fmt = sniff_format(head)
            w = h = None
            if fmt == "png" and len(head) >= 24:
                w, h = struct.unpack(">II", head[16:24])
            elif fmt == "jpeg":
                f.seek(2)
                while True:
                    b = f.read(1)
                    while b and b != b"\xff":
                        b = f.read(1)
                    while b == b"\xff":
                        b = f.read(1)
                    if not b:
                        break
                    marker = b[0]
                    if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                        continue
                    seg = f.read(2)
                    if len(seg) < 2:
                        break
                    (ln,) = struct.unpack(">H", seg)
                    if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                        data = f.read(5)
                        if len(data) == 5:
                            h, w = struct.unpack(">HH", data[1:5])
                        break
                    f.seek(ln - 2, 1)
            elif fmt == "bmp" and len(head) >= 26:
                w, h = struct.unpack("<ii", head[18:26])
                h = abs(h)
            return {"format": fmt, "width": w, "height": h}
    except OSError:
        return {"format": None, "width": None, "height": None, "unreadable": True}


def _sha1(path: Path) -> str:
    h = hashlib.sha1()  # noqa: S324  (duplicate detection, not security)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _pillow():
    try:
        from PIL import Image  # noqa: PLC0415  (optional dependency)
        return Image
    except ImportError:
        return None


def dhash(path: Path) -> int | None:
    """64-bit difference hash (9x8 grayscale thumbnail). None if the image cannot be decoded or Pillow is missing."""
    Image = _pillow()
    if Image is None:
        return None
    try:
        with Image.open(path) as im:
            im.draft("L", (64, 64))                 # cheap JPEG downscale at decode time
            g = im.convert("L").resize((9, 8))
            px = list(g.tobytes())                  # mode "L": one byte per pixel
    except Exception:           # noqa: BLE001  (corrupt/unsupported file: counted by the caller, never fatal)
        return None
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (px[row * 9 + col] > px[row * 9 + col + 1])
    return bits


def _dist(vals: list[float]) -> dict:
    if not vals:
        return {"n": 0}
    s = sorted(vals)
    q = lambda p: s[min(len(s) - 1, int(p * (len(s) - 1)))]  # noqa: E731
    return {"n": len(s), "min": s[0], "p25": q(0.25), "median": q(0.5), "p75": q(0.75), "max": s[-1], "mean": round(statistics.fmean(s), 2)}


def image_files_audit(root: Path, relpaths: Sequence[str], *, group_of: Callable[[str], str | None] | None = None, split_of: Callable[[str], str | None] | None = None,
                      max_files: int = 50_000, max_near_dup_images: int = 6000, near_hamming: int = NEAR_HAMMING, examples: int = 5) -> dict:
    """Header/duplicate audit of the files behind prepared image records. ``relpaths`` are relative to ``root``."""
    root = Path(root)
    rels = sorted(set(relpaths))
    capped = len(rels) > max_files
    use = rels[:max_files]
    fmts: Counter = Counter()
    ext: Counter = Counter()
    ext_mismatch: Counter = Counter()
    dims: Counter = Counter()
    widths, heights, sizes = [], [], []
    missing = unreadable = 0
    sha: dict[str, list[str]] = defaultdict(list)
    for rel in use:
        p = root / rel
        if not p.is_file():
            missing += 1
            continue
        e = p.suffix.lower().lstrip(".") or "(none)"
        ext[e] += 1
        info = read_image_header(p)
        if info.get("unreadable"):
            unreadable += 1
            continue
        f = info["format"]
        fmts[f or "unrecognised"] += 1
        if f and f.replace("jpeg", "jpg") != e.replace("jpeg", "jpg"):
            ext_mismatch[f"{e}->{f}"] += 1
        if info["width"] and info["height"]:
            dims[f"{info['width']}x{info['height']}"] += 1
            widths.append(info["width"])
            heights.append(info["height"])
        sizes.append(p.stat().st_size)
        sha[_sha1(p)].append(rel)
    dup_groups = [v for v in sha.values() if len(v) > 1]
    exact = {"duplicate_clusters": len(dup_groups), "files_in_duplicate_clusters": sum(len(v) for v in dup_groups), "examples": [v[:3] for v in dup_groups[:examples]]}
    cross = lambda cl: (len({group_of(r) if group_of else None for r in cl} - {None}) > 1,  # noqa: E731
                        len({split_of(r) if split_of else None for r in cl} - {None}) > 1)
    if group_of or split_of:
        c = [cross(v) for v in dup_groups]
        exact["clusters_spanning_groups"] = sum(a for a, _ in c)
        exact["clusters_spanning_train_and_holdout"] = sum(b for _, b in c)

    near: dict = {"status": "unavailable", "reason": "Pillow is not installed: near-duplicate (perceptual hash) check was NOT run"}
    if _pillow() is not None:
        sub = rels[:max_near_dup_images]
        hashes: list[tuple[str, int]] = []
        failed = 0
        for rel in sub:
            h = dhash(root / rel)
            if h is None:
                failed += 1
            else:
                hashes.append((rel, h))
        pairs, twin_imgs, adj = [], set(), 0
        for i in range(len(hashes)):
            ri, hi = hashes[i]
            for j in range(i + 1, len(hashes)):
                if (hi ^ hashes[j][1]).bit_count() <= near_hamming:
                    pairs.append((ri, hashes[j][0]))
                    twin_imgs.update((ri, hashes[j][0]))
                    adj += j == i + 1
        near = {"status": "ok", "images_hashed": len(hashes), "images_failed_to_decode": failed, "capped_to_first_n_by_path": len(rels) > max_near_dup_images,
                "hamming_threshold_bits_of_64": near_hamming, "near_duplicate_pairs": len(pairs), "images_with_a_near_twin": len(twin_imgs),
                "share_with_near_twin": round(len(twin_imgs) / max(len(hashes), 1), 4), "adjacent_in_path_order_pairs": adj,
                "examples": [list(p) for p in pairs[:examples]],
                "note": "Covers the first N images in path order, not a census; a high share means frames are near-identical (video-derived or burst shots), so random splits would leak."}
        if group_of or split_of:
            near["pairs_spanning_groups"] = sum(1 for a, b in pairs if group_of and group_of(a) != group_of(b) and None not in (group_of(a), group_of(b)))
            near["pairs_spanning_train_and_holdout"] = sum(1 for a, b in pairs if split_of and None not in (split_of(a), split_of(b)) and split_of(a) != split_of(b))
    return {"files_audited": len(use), "files_total": len(rels), "capped_to_first_n_by_path": capped, "missing_files": missing, "unreadable_files": unreadable,
            "extensions": dict(ext.most_common()), "formats_by_magic_bytes": dict(fmts.most_common()), "extension_vs_content_mismatch": dict(ext_mismatch.most_common(5)),
            "distinct_dimensions": len(dims), "top_dimensions": dims.most_common(5), "width": _dist(widths), "height": _dist(heights), "file_bytes": _dist(sizes),
            "exact_duplicates": exact, "near_duplicates": near}


def annotation_audit(records: Iterable, *, box_names: bool = True) -> dict:
    """Class distribution, annotation completeness and box statistics from prepared ImageRecord-like objects."""
    recs = list(records)
    raw, mapped, per_image_boxes, rel_area = Counter(), Counter(), [], []
    status_by_class: dict[str, Counter] = defaultdict(Counter)
    ann = unann = no_box = 0
    img_labels: Counter = Counter()
    for r in recs:
        if not r.has_annotation:
            unann += 1
            continue
        ann += 1
        no_box += not r.boxes and not r.source_labels
        per_image_boxes.append(len(r.boxes))
        img_labels.update(r.image_labels or ["(none mapped)"])
        for lab in r.source_labels if not r.boxes else []:
            raw[lab] += 1
        for b in r.boxes:
            raw[b.class_code] += 1
            mapped[f"{b.category}/{b.subcategory}" if b.subcategory else (b.category or "(unmapped)")] += 1
            status_by_class[b.class_code][b.mapping_status] += 1
            if r.width and r.height and not b.normalized:
                rel_area.append(round((b.xmax - b.xmin) * (b.ymax - b.ymin) / (r.width * r.height), 5))
            elif b.normalized:
                rel_area.append(round((b.xmax - b.xmin) * (b.ymax - b.ymin), 5))
    return {"images": len(recs), "annotated_images": ann, "images_without_annotation": unann, "annotated_images_with_no_boxes_or_labels": no_box,
            "source_class_counts": dict(raw.most_common()), "mapped_box_label_counts": dict(mapped.most_common()),
            "mapping_status_by_source_class": {k: dict(v) for k, v in status_by_class.items()},
            "image_level_mapped_label_counts": dict(img_labels.most_common()), "boxes_per_annotated_image": _dist([float(x) for x in per_image_boxes]),
            "box_area_fraction_of_image": _dist(rel_area) if rel_area else {"n": 0, "note": "image sizes unknown or no boxes"},
            "note": ("A pothole-only dataset has no negatives: precision is not meaningful. 'unannotated' means no label file was found — NOT that the image shows a good road."
                     if box_names else "")}


def group_audit(records: Iterable, *, examples: int = 5) -> dict:
    recs = list(records)
    groups: dict[str, list] = defaultdict(list)
    ungrouped = 0
    for r in recs:
        if r.group_id is None:
            ungrouped += 1
        else:
            groups[r.group_id].append(r)
    sizes = [len(v) for v in groups.values()]
    straddle = [g for g, v in groups.items() if {"train"} <= {x.split_hint for x in v} and any(x.split_hint in ("holdout", "test", "val") for x in v)]
    return {"n_groups": len(groups), "images_without_group": ungrouped, "group_size": _dist([float(s) for s in sizes]),
            "singleton_groups": sum(s == 1 for s in sizes), "largest_groups": Counter({g: len(v) for g, v in groups.items()}).most_common(examples),
            "groups_straddling_train_and_holdout": len(straddle), "straddle_examples": sorted(straddle)[:examples],
            "split_counts": dict(Counter(r.split_hint or "none" for r in recs))}


def video_frame_relationships(profile: dict) -> dict:
    """Facts about video/frame structure from ``profile_image_dataset`` output (no guessing about which frames come from which video)."""
    n_vid, n_img = profile.get("n_videos", 0), profile.get("n_images", 0)
    msgs = []
    if n_vid and n_img:
        msgs.append(f"{n_vid} video file(s) AND {n_img} image(s): whether the images were extracted from these videos is NOT established by file structure alone; "
                    "check the dataset's documentation before assuming independence.")
    if n_vid and not n_img:
        msgs.append("videos only: frames must be extracted externally (keeping the video id in the file name) before any image evaluation.")
    if not n_vid and profile.get("numbered_filename_share", 0) > 0.8:
        msgs.append("most file names end in a number (frame/sequence index): frames may be consecutive captures; use a block or regex group rule for holdouts.")
    return {"n_videos": n_vid, "n_images": n_img, "numbered_filename_share": profile.get("numbered_filename_share"), "observations": msgs}
