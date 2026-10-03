"""Evaluation / export helpers for notebook 06 (they take Ultralytics objects; ultralytics itself is imported by the notebook, never here)."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import random
import shutil
import sys
import zipfile
from pathlib import Path

from . import yolo_data as yd

NAMES = dict(enumerate(yd.CLASSES))


def _val(best, data, imgsz, batch, dev, split=None):
    kw = {"split": split} if split else {}
    return best.val(data=str(data), imgsz=imgsz, batch=batch, plots=False, verbose=False, workers=0, **kw, **dev)


def evaluate_test_groups(best, data_dir: Path, work: Path, *, imgsz: int, batch: int, dev: dict, min_images: int = 30) -> dict:
    """Held-out TEST groups: overall, per class, per country (file-name prefix) and per source."""
    ev: dict = {"overall": {}, "per_class": {}, "per_country": {}, "per_source": {}}
    r = _val(best, data_dir / "data.yaml", imgsz, batch, dev, split="test")
    ev["overall"] = {"mAP50": round(float(r.box.map50), 4), "mAP50-95": round(float(r.box.map), 4), "precision": round(float(r.box.mp), 4), "recall": round(float(r.box.mr), 4)}
    for i, cls_idx in enumerate(r.box.ap_class_index):
        ev["per_class"][NAMES[int(cls_idx)]] = {"AP50": round(float(r.box.ap50[i]), 4), "AP50-95": round(float(r.box.ap[i]), 4)}
    by_country: dict[str, list] = {}
    by_source: dict[str, list] = {}
    for p in sorted((data_dir / "images" / "test").iterdir()):
        src, stem = p.stem.split("__", 1)
        by_source.setdefault(src, []).append(p)
        by_country.setdefault("India (BharatPotHole)" if src == "bharatpothole" else stem.split("_")[0], []).append(p)
    for label, group in (("country", by_country), ("source", by_source)):
        for k, files in sorted(group.items()):
            if len(files) < min_images:
                continue
            tag = "".join(ch if ch.isalnum() else "_" for ch in f"{label}_{k}")
            lst, y = work / f"test_{tag}.txt", work / f"data_{tag}.yaml"
            lst.write_text("\n".join(str(p) for p in files) + "\n", encoding="utf-8")
            y.write_text(f"path: {data_dir}\ntrain: images/train\nval: {lst}\nnames:\n" + "".join(f"  {i}: {n}\n" for i, n in NAMES.items()), encoding="utf-8")
            rr = _val(best, y, imgsz, batch, dev)
            ev["per_" + label][k] = {"images": len(files), "mAP50": round(float(rr.box.map50), 4), "recall": round(float(rr.box.mr), 4)}
    return ev


def domain_check(best, root: Path, *, imgsz: int, dev: dict, seed: int = 42, per_scene: int = 60) -> dict:
    """Photos of a different kind (Maharashtra, folder-named only, no boxes): share of sampled images with a pothole (D40) detection at conf >= 0.25 per scene
    folder. Only ``Final`` folders are sampled (RAW/Final/Rotated hold the same photos)."""
    rng, scenes = random.Random(seed), {}
    for p in sorted(Path(root).rglob("*")):
        if p.suffix.lower() in (".jpg", ".jpeg", ".png") and "final" in [q.lower() for q in p.parts[:-1]]:
            scenes.setdefault(p.parent.parent.name, []).append(p)
    out = {}
    for scene, files in sorted(scenes.items()):
        sample = rng.sample(files, min(per_scene, len(files)))
        res = best.predict([str(f) for f in sample], imgsz=imgsz, conf=0.25, verbose=False, stream=False, **dev)
        hits = sum(any(int(c) == 3 for c in r.boxes.cls.tolist()) for r in res)
        out[scene] = {"sampled": len(sample), "pothole_detected_share": round(hits / len(sample), 3), "folder_says_pothole": "pothole" in scene.lower()}
    return out


def load_backend_vision(repo: Path):
    """The backend's detector module, loaded by path (it needs only numpy / Pillow / onnxruntime, not the FastAPI stack)."""
    spec = importlib.util.spec_from_file_location("civic_vision", Path(repo) / "backend" / "ai_gateway" / "vision.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["civic_vision"] = mod
    spec.loader.exec_module(mod)
    return mod


def decoder_parity(vision_mod, onnx_file: Path, onnx_yolo, images: list[Path], *, imgsz: int, dev: dict, limit: int = 40) -> dict:
    """The backend's numpy decoder vs Ultralytics' own predictor on the exported file: how often the top detection's class agrees."""
    det = vision_mod.OnnxRoadDamageDetector(onnx_file, conf=0.25, iou=0.45)
    checked = agree = 0
    for p in images[:limit]:
        mine = det.detect(p.read_bytes(), p.name).detections
        theirs = onnx_yolo.predict(str(p), imgsz=imgsz, conf=0.25, iou=0.45, verbose=False, **dev)[0]
        if mine or len(theirs.boxes):
            checked += 1
            top = NAMES[int(theirs.boxes.cls[int(theirs.boxes.conf.argmax())])] if len(theirs.boxes) else None
            agree += int(bool(mine) and mine[0].class_code == top)
    return {"images_with_detections": checked, "top1_class_agreement": agree}


def write_bundle(work: Path, out_dir: Path, card: dict, files: list[Path]) -> Path:
    out_dir.mkdir(exist_ok=True)
    for f in files:
        if f and Path(f).exists():
            shutil.copy(f, out_dir / Path(f).name)
    (out_dir / "model_card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    bundle = work / f"civic_road_damage_{card['version']}.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(out_dir.iterdir()):
            z.write(f, f"road_damage/{f.name}")
    return bundle


def epoch_seconds(results_csv: Path) -> list[float]:
    """Wall-clock seconds of every epoch from Ultralytics' results.csv (its ``time`` column is cumulative; under DDP only rank 0 writes the file). [] if unavailable."""
    import csv
    try:
        with open(results_csv, newline="", encoding="utf-8") as f:
            rows = [{k.strip(): v for k, v in row.items() if k} for row in csv.DictReader(f)]
        cum = [float(r["time"]) for r in rows if (r.get("time") or "").strip()]
    except (OSError, KeyError, ValueError):
        return []
    return [round(b - a, 2) for a, b in zip([0.0, *cum], cum)]


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
