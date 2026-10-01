"""RDD2022 (PASCAL VOC road-damage annotations) -> ImageRecord.

Prepares *references* to externally stored images: only paths, sizes, boxes and mapped labels are
emitted; image bytes are never copied. Layout assumption (from the project README, not verified here):
``<root>/<Country...>/<split>/{images/*.jpg, annotations/xmls/*.xml}``. The adapter discovers files by
glob and infers country/capture context from path components, so small layout differences are tolerated.
Test-split images have no annotations and are skipped unless ``include_unannotated`` is set.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator

from ..canonical import BBox, ImageRecord, Provenance
from ..card_schema import SourceCard
from ..errors import SchemaMismatch
from ..mapping import CoverageReport, MappingTable

IMAGE_EXTS = (".jpg", ".jpeg", ".png")
COUNTRY_KEYWORDS = (("japan", "Japan"), ("india", "India"), ("czech", "Czech Republic"), ("norway", "Norway"),
                    ("united", "United States"), ("usa", "United States"), ("china", "China"))
CLASS_NAMES = {"D00": "longitudinal crack", "D10": "transverse crack", "D20": "alligator crack", "D40": "pothole"}


def infer_country(rel_parts: tuple[str, ...]) -> tuple[str | None, str | None]:
    lowered = [p.lower() for p in rel_parts]
    country = next((name for kw, name in COUNTRY_KEYWORDS if any(kw in p for p in lowered)), None)
    context = "MotorBike" if any("motorbike" in p for p in lowered) else "Drone" if any("drone" in p for p in lowered) else None
    return country, context


_TRAILING_INT = re.compile(r"(\d+)$")


def block_group(country: str | None, context: str | None, split: str | None, stem: str, block_size: int) -> str:
    """Group id for leakage-aware holdouts: consecutive frame numbers are usually the same drive, so whole index blocks
    (not single frames) are the unit that must stay on one side of a split. A HEURISTIC: frame numbering is not verified
    to follow drive order."""
    m = _TRAILING_INT.search(stem)
    block = f"{int(m.group(1)) // block_size}" if m else "nogroup"
    return f"{country or 'unknown'}:{context or '-'}:{split or '-'}:{block}"


def parse_voc(xml_path: Path) -> dict:
    raw = Path(xml_path).read_bytes()
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:       # entity-expansion / external-entity hardening
        raise SchemaMismatch(f"refusing XML with DTD/entities: {xml_path.name}")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        raise SchemaMismatch(f"invalid XML {xml_path.name}: {e}") from e
    size = root.find("size")
    w = int(float(size.findtext("width", "0"))) if size is not None else 0
    h = int(float(size.findtext("height", "0"))) if size is not None else 0
    objs = []
    for o in root.findall("object"):
        bb = o.find("bndbox")
        if bb is None:
            continue
        try:
            objs.append({"name": (o.findtext("name") or "").strip(),
                         "box": [float(bb.findtext(k, "nan")) for k in ("xmin", "ymin", "xmax", "ymax")]})
        except ValueError:
            continue
    return {"filename": (root.findtext("filename") or "").strip(), "width": w or None, "height": h or None, "objects": objs}


class RDD2022Adapter:
    source_id = "rdd2022"

    def __init__(self, card: SourceCard, mapping: MappingTable, *, retrieved_at: str | None = None, block_size: int = 100):
        self.card, self.mapping, self.retrieved_at = card, mapping, retrieved_at
        self.block_size = block_size
        self.coverage = CoverageReport()          # over boxes
        self.stats = {"xml_files": 0, "images_missing": 0, "degenerate_boxes": 0, "unknown_classes": 0, "invalid_xml": 0}

    def provenance(self, rid: str) -> Provenance:
        return Provenance(kind="real_public", source_id=self.card.id, source_dataset=self.card.name,
                          source_version=self.card.version_note[:120], source_record_id=rid, license_id=self.card.license.name[:120],
                          license_verified=self.card.license_verified, origin_verified=self.card.origin_verified, label_origin="human_annotated",
                          mapping_id=self.mapping.mapping_id, mapping_version=self.mapping.version, retrieved_at=self.retrieved_at)

    def _image_for(self, xml_path: Path, filename: str) -> Path | None:
        for images_dir in (xml_path.parents[2] / "images", xml_path.parents[1] / "images", xml_path.parent / "images"):
            for cand in ([images_dir / filename] if filename else []) + [images_dir / f"{xml_path.stem}{e}" for e in IMAGE_EXTS]:
                if cand.is_file():
                    return cand
        return None

    def iter_records(self, root, *, countries: set[str] | None = None, check_images: bool = False,
                     include_unannotated: bool = False, max_images: int | None = None) -> Iterator[ImageRecord]:
        root = Path(root)
        if not root.is_dir():
            raise SchemaMismatch(f"dataset root not found: {root}")
        n = 0
        for xml_path in sorted(root.rglob("*.xml")):
            if "annotations" not in {p.lower() for p in xml_path.parts}:
                continue
            self.stats["xml_files"] += 1
            rel = xml_path.relative_to(root)
            country, context = infer_country(rel.parts)
            if countries and country not in countries:
                continue
            try:
                ann = parse_voc(xml_path)
            except SchemaMismatch:
                self.stats["invalid_xml"] += 1
                continue
            img = self._image_for(xml_path, ann["filename"])
            if img is None:
                self.stats["images_missing"] += 1
                if check_images:
                    continue
                img_rel = str((xml_path.parents[2] / "images" / (ann["filename"] or f"{xml_path.stem}.jpg")).relative_to(root))
            else:
                img_rel = str(img.relative_to(root))
            boxes: list[BBox] = []
            labels: set[str] = set()
            for o in ann["objects"]:
                x0, y0, x1, y1 = o["box"]
                if not (x1 > x0 and y1 > y0):
                    self.stats["degenerate_boxes"] += 1
                    continue
                res = self.mapping.map(class_code=o["name"])
                if o["name"] not in CLASS_NAMES:
                    self.stats["unknown_classes"] += 1
                self.coverage.add(res, o["name"])
                boxes.append(BBox(class_code=o["name"], class_name=CLASS_NAMES.get(o["name"]), xmin=x0, ymin=y0, xmax=x1, ymax=y1,
                                  category=res.category, subcategory=res.subcategory, mapping_status=res.status))
                if res.category:
                    labels.add(f"{res.category}/{res.subcategory}" if res.subcategory else res.category)
            low_parts = {p.lower() for p in rel.parts}
            split = "train" if "train" in low_parts else "test" if any(p.startswith("test") for p in low_parts) else "val" if "val" in low_parts else None
            yield ImageRecord(record_id=f"{self.card.id}:{country or 'unknown'}:{context or '-'}:{xml_path.stem}", provenance=self.provenance(xml_path.stem),
                              image_relpath=img_rel, width=ann["width"], height=ann["height"], country=country, capture_context=context,
                              has_annotation=True, boxes=boxes, image_labels=sorted(labels),
                              source_labels=sorted({b.class_code for b in boxes}), group_id=block_group(country, context, split, xml_path.stem, self.block_size),
                              split_hint=split)
            n += 1
            if max_images and n >= max_images:
                return
        if include_unannotated:
            seen = {}
            for img in sorted(p for p in root.rglob("*") if p.suffix.lower() in IMAGE_EXTS and p.parent.name.lower() == "images"):
                rel = img.relative_to(root)
                xml = img.parents[1] / "annotations" / "xmls" / f"{img.stem}.xml"
                country, context = infer_country(rel.parts)
                if xml.exists() or (countries and country not in countries) or seen.get(rel) is not None:
                    continue
                yield ImageRecord(record_id=f"{self.card.id}:{country or 'unknown'}:{context or '-'}:{img.stem}", provenance=self.provenance(img.stem),
                                  image_relpath=str(rel), country=country, capture_context=context, has_annotation=False,
                                  group_id=block_group(country, context, None, img.stem, self.block_size))
