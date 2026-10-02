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
    urls: tuple[str, ...]                # the exact sources this notebook was written for
    attach: str                          # how to attach it in Kaggle
    layout: str                          # what the notebook expects to see under the mount (stated as a hint, NOT enforced beyond "images exist")


SPECS: dict[str, DatasetSpec] = {s.id: s for s in (
    DatasetSpec(
        "bmc_mumbai", "BMC Mumbai civic complaints (Kaggle competition; SYNTHETIC)", "tabular",
        ("mumbainagarsevabmccivic", "mumbainagarseva", "bmccivic", "bmccomplaint"),
        ("https://www.kaggle.com/competitions/mumbai-nagar-seva-bmc-civic-complaint-resolution-2018-2024/data",
         "https://www.kaggle.com/competitions/mumbai-nagar-seva-bmc-civic-complaint-resolution-2018-2024/rules"),
        "Notebook → Add Input → Competition data → 'Mumbai Nagar Seva / BMC Civic Complaint Resolution 2018-2024' (accept the competition rules first).",
        "…/bmc_train.csv (the only file read for data), bmc_data_dictionary.csv (read for column descriptions), bmc_test.csv (target withheld: NEVER opened)."),
    DatasetSpec(
        "mumbai_nashik_road_surface", "Mumbai/Nashik road-surface dataset v2 (Mendeley tj2m7zz4rg)", "images",
        ("mumbainashik", "nashikmumbai", "roadsurface", "tj2m7zz4rg", "roadsurfaceimages", "nashik"),
        ("https://data.mendeley.com/datasets/tj2m7zz4rg/2",),
        "The authors do not host it on Kaggle, and a Mendeley PAGE URL is not a data file (a 'remote file' import of it stores only the HTML page). Create a PRIVATE Kaggle Dataset from the actual data (version 2): either a "
        "direct file/zip URL (Mendeley's public zip endpoint https://data.mendeley.com/public-api/zip/tj2m7zz4rg/download/2 — unverified from here) or the zip you download from the Mendeley page and upload; keep the attribution/licence text.",
        "/kaggle/input/<your-dataset>/… images, videos and any annotation files. The layout is NOT assumed: the profile reports what exists."),
    DatasetSpec(
        "rdd2022", "RDD2022 — Kaggle copy aliabdelmenam/rdd-2022", "images", ("rdd2022",),
        ("https://www.kaggle.com/datasets/aliabdelmenam/rdd-2022",),
        "Notebook → Add Input → search 'aliabdelmenam/rdd-2022' and add THAT dataset itself (a THIRD-PARTY re-upload of the upstream RDD2022 project; its provenance and licence must be re-checked). Do NOT create your own dataset from the page URL: that stores only the HTML landing page.",
        "/kaggle/input/rdd-2022/… (or /kaggle/input/datasets/aliabdelmenam/rdd-2022/…). Its layout, annotation format, class list, countries and splits are NOT assumed: "
        "the profile reports what exists and you then set IMAGE['rdd2022'] (e.g. a countries filter for the India subset)."),
    DatasetSpec(
        "rdd2020", "RDD2020 (Mendeley 5ty2wb6gvg v1) — India subset where applicable", "images", ("rdd2020",),
        ("https://data.mendeley.com/datasets/5ty2wb6gvg/1",),
        "A Mendeley PAGE URL is not a data file (a 'remote file' import stores only the HTML page). Create a private Kaggle Dataset whose name contains 'rdd2020' from the actual data: a direct zip URL "
        "(https://data.mendeley.com/public-api/zip/5ty2wb6gvg/download/1 — unverified from here) or the downloaded zip; the India subset is enough.",
        "/kaggle/input/<name containing rdd2020>/… The layout is NOT assumed: the profile reports what exists; use a countries filter if several countries are present."),
    DatasetSpec(
        "bharatpothole", "BharatPotHole (iWatchRoad)", "images", ("bharatpothole", "iwatchroad"),
        ("https://www.kaggle.com/datasets/surbhisaswatimohanty/bharatpothole",),
        "Notebook → Add Input → search 'surbhisaswatimohanty/bharatpothole' and add THAT dataset itself. Do NOT create your own dataset from the page URL: that stores only the HTML landing page.",
        "/kaggle/input/bharatpothole/… frames + annotations. Format, class-names file and grouping are NOT assumed: the profile reports what exists."),
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


_KNOWN_EXTS = IMAGE_EXTS | TABULAR_EXTS | {".xml", ".txt", ".yaml", ".yml", ".names", ".mp4", ".avi", ".mov", ".mkv", ".mpg", ".mpeg", ".wmv", ".md", ".pdf"}
MAX_SNIFFS = 400


def scan_tree(path: Path, cap: int = SCAN_FILE_CAP) -> dict:
    """Bounded census of one mount: counts by extension, files whose TYPE was sniffed from their first bytes (extension-less or unknown files are
    often archives), archive files, top-level entries and a sample of files with sizes. Reads names and <= 512 bytes of unknown files only."""
    from .archive_tools import ARCHIVE_KINDS, sniff_kind, text_preview
    path = Path(path)
    ext: dict[str, int] = {}
    n = 0
    xml_in_annotations = 0
    ext_archives = 0
    tabular: list[dict] = []
    archive_files: list[dict] = []
    by_magic: dict[str, int] = {}
    sample: list[dict] = []
    sniffs = 0
    capped = False
    for p in path.rglob("*"):
        if not p.is_file():
            continue
        n += 1
        if n > cap:
            capped = True
            break
        e = p.suffix.lower()
        ext[e or "(none)"] = ext.get(e or "(none)", 0) + 1
        try:
            size = p.stat().st_size
        except OSError:
            size = -1
        ext_archives += e in (".zip", ".tar", ".tgz", ".7z", ".rar")
        if e == ".xml" and "annotations" in {x.lower() for x in p.parts}:
            xml_in_annotations += 1
        if e in TABULAR_EXTS and len(tabular) < 50:
            tabular.append({"relpath": str(p.relative_to(path)), "bytes": size})
        kind = None
        if e not in _KNOWN_EXTS and sniffs < MAX_SNIFFS:
            sniffs += 1
            kind = sniff_kind(p)
            by_magic[kind or "unrecognised"] = by_magic.get(kind or "unrecognised", 0) + 1
            if kind in ARCHIVE_KINDS or e in (".zip", ".tar", ".tgz", ".7z", ".rar", ".gz"):
                archive_files.append({"relpath": str(p.relative_to(path)), "kind": kind, "bytes": size})
        elif e in (".zip", ".tar", ".tgz", ".7z", ".rar", ".gz") and len(archive_files) < 50:
            archive_files.append({"relpath": str(p.relative_to(path)), "kind": sniff_kind(p), "bytes": size})
        if len(sample) < 15:
            item = {"relpath": str(p.relative_to(path)), "bytes": size, "extension": e or "(none)", "content_type": kind}
            if kind in ("text", "html", "json", "xml") and 0 <= size <= 5_000_000 and sum("preview" in x for x in sample) < 3:
                item.update(text_preview(p))
            sample.append(item)
    top = []
    for c in sorted(path.iterdir())[:30]:
        top.append({"name": c.name, "type": "symlink" if c.is_symlink() else "dir" if c.is_dir() else "file",
                    "bytes": c.stat().st_size if c.is_file() else None})
    return {"files": n, "capped": capped, "extensions": dict(sorted(ext.items(), key=lambda kv: -kv[1])[:12]),
            "images": sum(v for k, v in ext.items() if k in IMAGE_EXTS), "xml_annotation_files": xml_in_annotations, "archives": max(ext_archives, len(archive_files)),
            "archive_files": archive_files, "content_types_of_unknown_files": by_magic, "top_level_entries": top, "sample_files": sample, "tabular_files": tabular}


def census_text(st: dict) -> str:
    """One-paragraph human description of what a mount actually contains (used in every 'not usable' message)."""
    tops = ", ".join(f"{e['name']} ({e['type']}{', ' + format(e['bytes'] / 1e6, '.1f') + ' MB' if e['bytes'] else ''})" for e in st["top_level_entries"][:8]) or "nothing"
    previews = [f"{x['relpath']}: {x.get('html_title') or x['preview'][:100]!r}" for x in st["sample_files"] if x.get("preview")][:3]
    return (f"it contains {st['files']} file(s); top-level entries: {tops}; extensions {st['extensions']}; previews {previews or 'n/a'}; "
            f"content types of unrecognised files {st['content_types_of_unknown_files'] or 'n/a'}; archives {[(a['relpath'], a['kind']) for a in st['archive_files'][:5]] or 'none'}")


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
    """Minimal usability check only. Format/layout questions are answered by the profile, never assumed here."""
    if st["files"] == 0:
        return "the mount is empty (no files)"
    if spec.kind == "tabular":
        if not st["tabular_files"]:
            return f"no CSV/JSON(L) data file found; {census_text(st)}"
        return None
    if st["images"] == 0:
        if any(a["kind"] in ("zip", "tar", "gzip", "bzip2", "xz") for a in st["archive_files"]):
            return None                                         # usable: profiled from the archive listing; extraction is an explicit opt-in
        why = "no image files found"
        pages = [x for x in st["sample_files"] if x.get("content_type") == "html"]
        if pages:
            titles = [x.get("html_title") or x["preview"][:60] for x in pages[:2]]
            why += (f" — the mount contains only a saved WEB PAGE ({', '.join(repr(t) for t in titles)}), i.e. the dataset's landing page, not its data. "
                    "This happens when a Kaggle dataset is created from a page URL ('remote file'). Re-attach the original Kaggle dataset, or create the dataset from the actual data file(s)")
        elif any(a["kind"] in ("7z", "rar") for a in st["archive_files"]):
            why += " — the archive is 7z/rar, which is not supported (re-upload it as zip or tar)"
        elif st["extensions"].get(".mp4") or st["extensions"].get(".avi"):
            why += " (videos only? frames must be extracted first)"
        return f"{why}; {census_text(st)}"
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
            rejected.append({"mount": str(d), "problem": prob, "census": {k: st[k] for k in ("files", "extensions", "content_types_of_unknown_files", "archive_files", "top_level_entries", "sample_files")}})
            continue
        return Location(spec.id, True, d, "name+structure", attached=attached, structure=st)
    if rejected:
        msg = f"NOT USABLE: {spec.title}: attached input(s) match the name but fail the structure check: " + "; ".join(f"{x['mount']} → {x['problem']}" for x in rejected) + f". Expected: {spec.layout}"
    else:
        msg = (f"NOT FOUND: {spec.title}. No directory under {r} has a name containing any of {list(spec.name_hints)}. "
               f"Attached right now: {attached or 'nothing'}. HOW TO ATTACH: {spec.attach} EXPECTED LAYOUT: {spec.layout} "
               "(or pass an explicit path in the notebook's PATHS dict).")
    return Location(spec.id, False, Path(rejected[0]["mount"]) if rejected else None, "", candidates_rejected=rejected, attached=attached, message=msg,
                    structure=rejected[0]["census"] if rejected else {})


def _is_test_file(name: str) -> bool:
    return "test" in name.lower()


def pick_tabular_file(location: Location, explicit: str | Path | None = None) -> tuple[Path | None, str]:
    """The ONE data file to profile. Never chosen silently when ambiguous, and a file that looks like the withheld-target TEST file is
    refused outright (even when named explicitly). Returns (path, explanation)."""
    if explicit:
        p = Path(explicit)
        if _is_test_file(p.name):
            return None, f"refused: {p.name} looks like the TEST file (its target is withheld; it is never used for target-bearing training or evaluation)."
        return (p, "explicit path") if p.is_file() else (None, f"explicit file not found: {p}")
    if location.path is None:
        return None, "dataset not located"
    files = [f for f in location.structure.get("tabular_files", []) if "dictionary" not in Path(f["relpath"]).name.lower()]
    train = [f for f in files if "train" in Path(f["relpath"]).name.lower() and not _is_test_file(Path(f["relpath"]).name)]
    if len(train) == 1:
        return location.path / train[0]["relpath"], "the only non-dictionary file whose name contains 'train' (test files are never opened)"
    cands = [f["relpath"] for f in (train or [f for f in files if not _is_test_file(Path(f["relpath"]).name)])]
    return None, (f"cannot choose the data file: {len(cands)} candidates {cands[:10]}. Set FILES['{location.dataset_id}'] to the training file "
                  "(the test file's target is withheld and must not be used).")


def find_data_dictionary(location: Location) -> Path | None:
    """The competition's data dictionary (a description of columns, not data rows), only if exactly one file looks like it."""
    if location.path is None:
        return None
    hits = [f for f in location.structure.get("tabular_files", []) if "dictionary" in Path(f["relpath"]).name.lower()]
    return location.path / hits[0]["relpath"] if len(hits) == 1 else None
