"""Locate attached Kaggle inputs (``/kaggle/input``) for each CivicConnect dataset and say EXACTLY what is missing.

Datasets stay in Kaggle's input storage and are read in place: nothing here copies, downloads or writes under the
input root (Kaggle mounts it read-only anyway). Discovery never guesses a dataset by luck:

1. an explicit override path (``overrides[dataset_id]``) wins, and must exist;
2. otherwise a mounted directory whose NAME contains one of the dataset's name hints is a candidate, and it must
   also pass the dataset's structural check (annotation folders / CSV files / images);
3. a directory that matches by name but fails the structure check is reported as such (never silently used);
4. nothing matches => a ``Location`` with ``found=False`` and a message listing what is attached and how to attach
   the missing dataset.

Kaggle mounts datasets as ``/kaggle/input/<slug>`` and, in newer layouts, ``/kaggle/input/datasets/<owner>/<slug>`` and
``/kaggle/input/competitions/<slug>``; all three are scanned. Slugs of third-party re-uploads (RDD2022/RDD2020 India,
the Mumbai/Nashik data) are NOT known to this repository, so those datasets are matched by name hints you can extend
or bypass with an override path.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_ROOT = Path("/kaggle/input")
ENV_ROOT = "CIVIC_KAGGLE_INPUT"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
TABULAR_EXTS = {".csv", ".tsv", ".jsonl", ".json", ".gz", ".csv.gz"}
SCAN_FILE_CAP = 1_000_000


def input_root(explicit: str | Path | None = None) -> Path:
    return Path(explicit or os.environ.get(ENV_ROOT) or DEFAULT_ROOT)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


@dataclass(frozen=True)
class DatasetSpec:
    id: str                              # == source card id
    title: str
    kind: str                            # "tabular" | "images"
    name_hints: tuple[str, ...]          # matched against normalised directory names (alphanumerics only)
    attach: str                          # how to attach it in Kaggle
    layout: str                          # what the notebook expects to see under the mount
    needs_xml_annotations: bool = False  # RDD-style: <...>/annotations/*.xml must exist
    default_format: str | None = None    # annotation format known from the dataset's own documentation (still verified by profiling)
    default_country: str | None = None


SPECS: dict[str, DatasetSpec] = {s.id: s for s in (
    DatasetSpec(
        "bmc_mumbai", "BMC Mumbai civic complaints (Kaggle competition; SYNTHETIC)", "tabular",
        ("mumbainagarsevabmccivic", "mumbainagarseva", "bmccivic", "bmccomplaint"),
        "Notebook → Add Input → Competition data → 'Mumbai Nagar Seva / BMC Civic Complaint Resolution 2018-2024' (accept the competition rules first).",
        "/kaggle/input/<competition-or-dataset>/…/*train*.csv (one training CSV; the test CSV has no target and is not used) and the data-dictionary CSV."),
    DatasetSpec(
        "mumbai_nashik_road_surface", "Mumbai/Nashik road-surface images (Mendeley tj2m7zz4rg)", "images",
        ("mumbainashik", "nashikmumbai", "roadsurface", "tj2m7zz4rg", "roadsurfaceimages", "nashik"),
        "Download the Mendeley files on a machine that can, upload them as a PRIVATE Kaggle Dataset (keep the attribution/licence text), then Add Input → Your Datasets. "
        "(The authors do not host it on Kaggle; this repository never downloads or copies it.)",
        "/kaggle/input/<your-dataset>/… images (+ any annotation files/folders + the videos). Layout is unknown until profiled: run the profile stage first."),
    DatasetSpec(
        "rdd2022", "RDD2022 — India subset", "images", ("rdd2022india", "rdd2022", "roaddamage2022"),
        "Upload the RDD2022 INDIA subset (from the project distribution) as a private Kaggle Dataset, or attach an existing Kaggle copy you trust; record who published that copy.",
        "/kaggle/input/<name containing 'rdd2022'>/…/India/train/{images/*.jpg, annotations/xmls/*.xml} (PASCAL VOC). If the mount IS the India folder, set default_country='India'.",
        needs_xml_annotations=True, default_format="voc", default_country="India"),
    DatasetSpec(
        "rdd2020", "RDD2020 — India subset", "images", ("rdd2020india", "rdd2020", "roaddamage2020"),
        "Upload the RDD2020 INDIA subset (Mendeley Data 5ty2wb6gvg) as a private Kaggle Dataset, or attach an existing copy you trust; record who published it.",
        "/kaggle/input/<name containing 'rdd2020'>/…/India/train/{images/*.jpg, annotations/xmls/*.xml} (PASCAL VOC). If the mount IS the India folder, set default_country='India'.",
        needs_xml_annotations=True, default_format="voc", default_country="India"),
    DatasetSpec(
        "bharatpothole", "BharatPotHole (iWatchRoad)", "images", ("bharatpothole", "iwatchroad"),
        "Notebook → Add Input → Datasets → search 'bharatpothole' (Kaggle: surbhisaswatimohanty/bharatpothole).",
        "/kaggle/input/bharatpothole/… dashcam frames + annotations (format reported as YOLO by a secondary source — NOT assumed: profile first; YOLO needs the dataset's own class-names file)."),
)}


@dataclass
class Location:
    dataset_id: str
    found: bool
    path: Path | None = None
    how: str = ""                                    # "override" | "name+structure"
    candidates_rejected: list[dict] = field(default_factory=list)
    attached: list[str] = field(default_factory=list)
    message: str = ""
    structure: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"dataset_id": self.dataset_id, "found": self.found, "path": str(self.path) if self.path else None, "how": self.how,
                "candidates_rejected": self.candidates_rejected, "attached_inputs": self.attached, "message": self.message, "structure": self.structure}


def mounted_dirs(root: Path, max_depth: int = 3) -> list[Path]:
    """Attached dataset directories: /kaggle/input/<slug>, /kaggle/input/{datasets/<owner>,competitions}/<slug>."""
    root = Path(root)
    if not root.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(root.iterdir()):
        if not p.is_dir():
            continue
        if p.name in ("datasets", "competitions") and max_depth >= 2:
            for q in sorted(p.iterdir()):
                if not q.is_dir():
                    continue
                if p.name == "datasets":                     # datasets/<owner>/<slug>
                    out.extend(sorted(x for x in q.iterdir() if x.is_dir()))
                else:
                    out.append(q)
        else:
            out.append(p)
    return out


def scan_tree(path: Path, cap: int = SCAN_FILE_CAP) -> dict:
    """Bounded file census of one mount (counts by extension, annotation folders, class-name-like files). Reads names only."""
    ext: dict[str, int] = {}
    n = 0
    xml_in_annotations = 0
    tabular: list[dict] = []
    capped = False
    for p in Path(path).rglob("*"):
        if not p.is_file():
            continue
        n += 1
        if n > cap:
            capped = True
            break
        e = p.suffix.lower()
        ext[e or "(none)"] = ext.get(e or "(none)", 0) + 1
        if e == ".xml" and "annotations" in {x.lower() for x in p.parts}:
            xml_in_annotations += 1
        if e in TABULAR_EXTS and len(tabular) < 50:
            tabular.append({"relpath": str(p.relative_to(path)), "bytes": p.stat().st_size})
    return {"files": n, "capped": capped, "extensions": dict(sorted(ext.items(), key=lambda kv: -kv[1])[:12]),
            "images": sum(v for k, v in ext.items() if k in IMAGE_EXTS), "xml_annotation_files": xml_in_annotations, "tabular_files": tabular}


def describe_inputs(root: Path | None = None) -> list[dict]:
    """What IS attached (names + coarse counts) — printed whenever something is missing so the cause is obvious."""
    r = input_root(root)
    out = []
    for d in mounted_dirs(r):
        s = scan_tree(d, cap=20000)
        out.append({"mount": str(d), "files_seen": s["files"], "capped": s["capped"], "images": s["images"], "xml_annotation_files": s["xml_annotation_files"],
                    "top_extensions": s["extensions"]})
    return out


def _structure_problem(spec: DatasetSpec, st: dict) -> str | None:
    if spec.kind == "tabular":
        if not st["tabular_files"]:
            return "no CSV/JSON(L) data file found under the mount"
        return None
    if spec.needs_xml_annotations and st["xml_annotation_files"] == 0:
        return "no PASCAL VOC annotation files (…/annotations/*.xml) found: this does not look like an RDD copy (or the annotations were not uploaded)"
    if st["images"] == 0 and st["files"] and not st["xml_annotation_files"]:
        return "no image files found under the mount (videos only? frames must be extracted first)"
    if st["images"] == 0 and st["files"] == 0:
        return "the mount is empty"
    return None


def locate(spec: DatasetSpec, root: Path | None = None, override: str | Path | None = None) -> Location:
    r = input_root(root)
    attached = [str(p.relative_to(r)) if r in p.parents else str(p) for p in mounted_dirs(r)]
    if override:
        p = Path(override)
        if not p.exists():
            return Location(spec.id, False, None, "override", attached=attached, message=f"NOT FOUND: the override path for {spec.id} does not exist: {p}. {spec.attach}")
        st = scan_tree(p)
        prob = _structure_problem(spec, st)
        if prob:
            return Location(spec.id, False, p, "override", attached=attached, structure=st, message=f"{spec.id}: override path {p} exists but fails the structure check: {prob}.")
        return Location(spec.id, True, p, "override", attached=attached, structure=st)
    if not r.is_dir():
        return Location(spec.id, False, None, "", attached=[], message=f"NOT FOUND: {spec.title}: the input root {r} does not exist (not running on Kaggle? set {ENV_ROOT} or pass an override path). {spec.attach}")
    hints = tuple(_norm(h) for h in spec.name_hints)
    rejected = []
    for d in mounted_dirs(r):
        key = _norm(d.name) + _norm(d.parent.name if d.parent != r else "")
        if not any(h in key for h in hints):
            continue
        st = scan_tree(d)
        prob = _structure_problem(spec, st)
        if prob:
            rejected.append({"mount": str(d), "problem": prob})
            continue
        return Location(spec.id, True, d, "name+structure", attached=attached, structure=st)
    if rejected:
        msg = f"NOT USABLE: {spec.title}: attached input(s) match the name but fail the structure check: " + "; ".join(f"{x['mount']} → {x['problem']}" for x in rejected) + f". Expected: {spec.layout}"
    else:
        msg = (f"NOT FOUND: {spec.title}. No directory under {r} has a name containing any of {list(spec.name_hints)}. "
               f"Attached right now: {attached or 'nothing'}. HOW TO ATTACH: {spec.attach} EXPECTED LAYOUT: {spec.layout} "
               "(or pass an explicit path in the notebook's PATHS dict).")
    return Location(spec.id, False, None, "", candidates_rejected=rejected, attached=attached, message=msg)


def pick_tabular_file(location: Location, explicit: str | Path | None = None) -> tuple[Path | None, str]:
    """The ONE data file to profile. Never chosen silently when ambiguous. Returns (path, explanation)."""
    if explicit:
        p = Path(explicit)
        return (p, "explicit path") if p.is_file() else (None, f"explicit file not found: {p}")
    if location.path is None:
        return None, "dataset not located"
    files = location.structure.get("tabular_files", [])
    train = [f for f in files if "train" in Path(f["relpath"]).name.lower()]
    if len(train) == 1:
        return location.path / train[0]["relpath"], "the only file whose name contains 'train'"
    cands = [f["relpath"] for f in (train or files)]
    return None, (f"cannot choose the data file: {len(cands)} candidates {cands[:10]}. Set FILES['{location.dataset_id}'] to the training file "
                  "(the test file's target is withheld and must not be used).")
