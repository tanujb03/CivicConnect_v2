"""Generic image-dataset adapter (VOC / YOLO / COCO / folder labels) for Indian road-image sources.

Used for BharatPotHole and the Mumbai/Nashik road-surface dataset. Nothing is guessed: the caller states the
annotation ``fmt``; YOLO needs class names from the dataset's own class file; unknown class names stay unmapped;
group ids (video / directory / index block) are derived by an explicit rule so that holdouts can keep whole groups
together. Only references (relative paths, boxes, labels) are emitted — never image bytes.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterator

from ..canonical import BBox, ImageRecord, Provenance
from ..card_schema import SourceCard
from ..errors import SchemaMismatch
from ..image_profile import CLASS_FILES, IMG, SPLIT_WORDS
from ..mapping import CoverageReport, MappingTable
from .rdd2022 import infer_country, parse_voc

FORMATS = ("voc", "yolo", "coco", "folder")
GROUP_RULES = ("dir", "regex", "block", "none")
LABEL_FROM = ("parent", "top", "all")
_TRAILING = re.compile(r"(\d+)$")
_GENERIC_DIRS = {"images", "image", "imgs", "labels", "label", "annotations", "annotation", "xmls", "xml", "jpegimages", "txt", "yolo", "voc"}


def load_class_names(path: Path) -> list[str]:
    """Class names from classes.txt / obj.names / .json (list or {"names": ...}) / data.yaml (names: [..] or block list/map)."""
    p = Path(path)
    if not p.is_file():
        raise SchemaMismatch(f"class names file not found: {p}")
    text = p.read_text(encoding="utf-8")
    if p.suffix == ".json":
        d = json.loads(text)
        names = d.get("names", d) if isinstance(d, dict) else d
        if isinstance(names, dict):
            return [names[k] for k in sorted(names, key=lambda x: int(x))]
        return [str(n) for n in names]
    if p.suffix in (".yaml", ".yml"):
        m = re.search(r"^names\s*:\s*\[(.*?)\]", text, re.M | re.S)
        if m:
            return [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()]
        block = re.search(r"^names\s*:\s*\n((?:[ \t]+.*\n?)+)", text, re.M)
        if block:
            items = []
            for line in block.group(1).splitlines():
                line = line.strip()
                if line.startswith("-"):
                    items.append(line[1:].strip().strip("'\""))
                elif ":" in line:
                    items.append(line.split(":", 1)[1].strip().strip("'\""))
            if items:
                return items
        raise SchemaMismatch(f"could not read 'names' from {p.name}; provide a .txt (one class per line) or .json list instead")
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


class DetectionDatasetAdapter:
    def __init__(self, card: SourceCard, mapping: MappingTable, *, fmt: str, class_names: list[str] | None = None, group_by: str = "dir",
                 group_regex: str | None = None, block_size: int = 100, label_from: str = "parent", retrieved_at: str | None = None,
                 countries: set[str] | None = None, default_country: str | None = None, split_from_path: bool = False,
                 holdout_splits: tuple[str, ...] = ("val", "test")):
        if fmt not in FORMATS:
            raise SchemaMismatch(f"--format is required and must be one of {FORMATS} (the adapter never guesses the annotation format)")
        if group_by not in GROUP_RULES:
            raise SchemaMismatch(f"group rule must be one of {GROUP_RULES}")
        if group_by == "regex" and not group_regex:
            raise SchemaMismatch("group_by=regex needs --group-regex with one capture group (e.g. the video id in the file name)")
        if label_from not in LABEL_FROM:
            raise SchemaMismatch(f"label_from must be one of {LABEL_FROM}")
        if fmt == "yolo" and not class_names:
            raise SchemaMismatch("YOLO labels hold numeric class ids: supply the dataset's own class names (--class-names-file); class names are never guessed")
        self.card, self.mapping, self.fmt, self.class_names = card, mapping, fmt, class_names
        self.group_by, self.group_re, self.block_size, self.label_from = group_by, re.compile(group_regex) if group_regex else None, block_size, label_from
        self.key = mapping.raw["match_fields"][0]
        self.retrieved_at = retrieved_at
        self.countries, self.default_country = countries, default_country
        self.split_from_path, self.holdout_splits = split_from_path, tuple(holdout_splits)
        self.coverage = CoverageReport()
        self.stats = {"images": 0, "annotated": 0, "unannotated_no_label_file": 0, "unknown_class_ids": 0, "degenerate_boxes": 0, "group_unparsed": 0,
                      "coco_files": 0, "invalid_files": 0, "ambiguous_annotation_match": 0, "filtered_out_by_country": 0, "country_unknown": 0,
                      "annotation_files_indexed": 0, "annotation_files_unused": 0}
        self._ann_index: dict[str, list[Path]] | None = None

    def provenance(self, rid: str) -> Provenance:
        c = self.card
        return Provenance(kind="real_public", source_id=c.id, source_dataset=c.name, source_version=c.version_note[:120], source_record_id=rid,
                          license_id=c.license.name[:120], license_verified=c.license_verified, origin_verified=c.origin_verified,
                          label_origin="human_annotated", mapping_id=self.mapping.mapping_id, mapping_version=self.mapping.version, retrieved_at=self.retrieved_at)

    # ------------------------------------------------------------------ helpers
    def _group(self, rel: Path) -> str | None:
        if self.group_by == "none":
            return None
        if self.group_by == "dir":
            return str(rel.parent) or "."
        if self.group_by == "regex":
            m = self.group_re.search(rel.stem)  # type: ignore[union-attr]
            if not m:
                self.stats["group_unparsed"] += 1
                return None
            return m.group(1) if m.groups() else m.group(0)
        m = _TRAILING.search(rel.stem)
        if not m:
            self.stats["group_unparsed"] += 1
            return None
        return f"{rel.parent}:{int(m.group(1)) // self.block_size}"

    def _box(self, name: str, x0: float, y0: float, x1: float, y1: float, normalized: bool) -> BBox | None:
        if not (x1 > x0 and y1 > y0):
            self.stats["degenerate_boxes"] += 1
            return None
        res = self.mapping.map(**{self.key: name})
        self.coverage.add(res, name)
        return BBox(class_code=name, class_name=name, xmin=x0, ymin=y0, xmax=x1, ymax=y1, category=res.category, subcategory=res.subcategory,
                    mapping_status=res.status, normalized=normalized)

    def _record(self, rel: Path, rid: str, boxes: list[BBox], source_labels: list[str], annotated: bool, size=(None, None)) -> ImageRecord:
        labels = set()
        for lab in source_labels:
            r = self.mapping.map(**{self.key: lab}) if not boxes else None
            if r is not None:
                self.coverage.add(r, lab)
                if r.category:
                    labels.add(f"{r.category}/{r.subcategory}" if r.subcategory else r.category)
        for b in boxes:
            if b.category:
                labels.add(f"{b.category}/{b.subcategory}" if b.subcategory else b.category)
        self.stats["images"] += 1
        self.stats["annotated"] += int(annotated)
        country, _ctx = infer_country(rel.parts)
        country = country or self.default_country
        self.stats["country_unknown"] += country is None
        return ImageRecord(record_id=f"{self.card.id}:{rid}", provenance=self.provenance(rid), image_relpath=str(rel), width=size[0], height=size[1],
                           country=country, has_annotation=annotated, boxes=boxes, image_labels=sorted(labels), source_labels=sorted(set(source_labels)),
                           group_id=self._group(rel), split_hint=self._split(rel))

    def _split(self, rel: Path) -> str | None:
        """Source split from a path component (train/val/test) ONLY when the operator opted in; held-out names become 'holdout'."""
        if not self.split_from_path:
            return None
        for part in rel.parts[:-1]:
            w = SPLIT_WORDS.get(part.lower())
            if w:
                return "holdout" if w in self.holdout_splits else "train"
        return None

    def _images(self, root: Path) -> list[Path]:
        out = []
        for p in sorted(root.rglob("*")):
            if not (p.is_file() and p.suffix.lower() in IMG):
                continue
            if self.countries:
                country, _ = infer_country(p.relative_to(root).parts)
                if (country or self.default_country) not in self.countries:
                    self.stats["filtered_out_by_country"] += 1
                    continue
            out.append(p)
        return out

    def _index(self, root: Path, suffix: str) -> dict[str, list[Path]]:
        """All annotation files of one kind by stem (case-insensitive folder names, any layout). Class-name files are not annotations."""
        idx: dict[str, list[Path]] = {}
        for p in root.rglob(f"*{suffix}"):
            if p.is_file() and p.name.lower() not in CLASS_FILES:
                idx.setdefault(p.stem, []).append(p)
        self.stats["annotation_files_indexed"] += sum(len(v) for v in idx.values())
        return idx

    def _match(self, img: Path, root: Path, idx: dict[str, list[Path]]) -> Path | None:
        """Annotation for an image: same stem; if several files share the stem pick the one sharing the most path components with the image
        (generic folder names like images/labels/annotations ignored). A tie is AMBIGUOUS: counted and left unannotated — never guessed."""
        cands = idx.get(img.stem, [])
        if len(cands) <= 1:
            return cands[0] if cands else None
        key = {x.lower() for x in img.relative_to(root).parts[:-1]} - _GENERIC_DIRS
        scored = sorted(((len(key & ({x.lower() for x in c.relative_to(root).parts[:-1]} - _GENERIC_DIRS)), c) for c in cands), key=lambda t: -t[0])
        if scored[0][0] > scored[1][0]:
            return scored[0][1]
        self.stats["ambiguous_annotation_match"] += 1
        return None

    # ------------------------------------------------------------------ formats
    def iter_records(self, root, *, max_images: int | None = None) -> Iterator[ImageRecord]:
        root = Path(root)
        if not root.is_dir():
            raise SchemaMismatch(f"dataset root not found: {root}")
        gen = {"voc": self._voc, "yolo": self._yolo, "coco": self._coco, "folder": self._folder}[self.fmt](root)
        for i, rec in enumerate(gen):
            if max_images and i >= max_images:
                return
            yield rec

    def _voc(self, root: Path):
        idx = self._index(root, ".xml")
        used: set[Path] = set()
        for img in self._images(root):
            xml = self._match(img, root, idx)
            rel = img.relative_to(root)
            if xml is None:
                self.stats["unannotated_no_label_file"] += 1
                yield self._record(rel, rel.with_suffix("").as_posix(), [], [], False)
                continue
            used.add(xml)
            try:
                ann = parse_voc(xml)
            except SchemaMismatch:
                self.stats["invalid_files"] += 1
                continue
            boxes = [b for o in ann["objects"] if (b := self._box(o["name"], *o["box"], False))]
            yield self._record(rel, rel.with_suffix("").as_posix(), boxes, [b.class_code for b in boxes], True, (ann["width"], ann["height"]))
        self.stats["annotation_files_unused"] += self.stats["annotation_files_indexed"] - len(used)

    def _yolo(self, root: Path):
        assert self.class_names
        idx = self._index(root, ".txt")
        used: set[Path] = set()
        for img in self._images(root):
            rel = img.relative_to(root)
            lab = self._match(img, root, idx)
            if lab is None:
                self.stats["unannotated_no_label_file"] += 1
                yield self._record(rel, rel.with_suffix("").as_posix(), [], [], False)
                continue
            used.add(lab)
            boxes: list[BBox] = []
            for line in lab.read_text(encoding="utf-8", errors="ignore").splitlines():
                f = line.split()
                if len(f) < 5:
                    continue
                try:
                    cid, cx, cy, w, h = int(float(f[0])), *map(float, f[1:5])
                except ValueError:
                    continue
                if not 0 <= cid < len(self.class_names):
                    self.stats["unknown_class_ids"] += 1
                    continue
                if (b := self._box(self.class_names[cid], cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, True)):
                    boxes.append(b)
            yield self._record(rel, rel.with_suffix("").as_posix(), boxes, [b.class_code for b in boxes], True)
        self.stats["annotation_files_unused"] += self.stats["annotation_files_indexed"] - len(used)

    def _coco(self, root: Path):
        files = []
        for p in sorted(root.rglob("*.json")):
            try:
                if p.stat().st_size > 500_000_000:
                    continue
                d = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(d, dict) and {"images", "annotations", "categories"} <= set(d):
                files.append((p, d))
        if not files:
            raise SchemaMismatch("no COCO-style JSON (images/annotations/categories) found under the root; check --format with `profile-images`")
        by_name: dict[str, Path] = {}
        for q in self._images(root):
            by_name.setdefault(q.name, q)
        for p, d in files:
            self.stats["coco_files"] += 1
            cats = {c["id"]: c["name"] for c in d["categories"]}
            by_img: dict = {}
            for a in d["annotations"]:
                by_img.setdefault(a["image_id"], []).append(a)
            for im in d["images"]:
                fn = im["file_name"]
                img = next((c for c in (p.parent / fn, root / fn) if c.is_file()), None) or by_name.get(Path(fn).name)
                rel = img.relative_to(root) if img is not None else Path(fn)      # unresolved file names stay as the dataset wrote them
                boxes = []
                for a in by_img.get(im["id"], []):
                    x, y, w, h = a["bbox"]
                    name = cats.get(a["category_id"])
                    if name is None:
                        self.stats["unknown_class_ids"] += 1
                        continue
                    if (b := self._box(name, x, y, x + w, y + h, False)):
                        boxes.append(b)
                yield self._record(rel, f"{p.stem}:{im['id']}", boxes, [b.class_code for b in boxes], True, (im.get("width"), im.get("height")))

    def _folder(self, root: Path):
        for img in self._images(root):
            rel = img.relative_to(root)
            comps = list(rel.parts[:-1])
            if not comps:
                self.stats["unannotated_no_label_file"] += 1
                yield self._record(rel, rel.with_suffix("").as_posix(), [], [], False)
                continue
            labels = {"parent": comps[-1:], "top": comps[:1], "all": comps}[self.label_from]
            yield self._record(rel, rel.with_suffix("").as_posix(), [], labels, True)
