"""Local road-damage detector (YOLO exported to ONNX) used by the intake gateway.

Independent of ``ai.training``: the class list and the civic mapping come from the ``model_card.json`` that notebook 06 writes next to ``best.onnx``.
Requires ``onnxruntime`` and ``Pillow``; both are optional — without them (or without ``AI_VISION_ONNX_PATH``) the gateway simply runs without a local image model.
It only ever PROPOSES: a detection becomes an additive ``image_analysis`` entry and, when no other AI answered, a low-confidence proposal the citizen must confirm.
"""
from __future__ import annotations

import io
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np

log = logging.getLogger("civicconnect.vision")

DEFAULT_CLASSES = ["D00", "D10", "D20", "D40"]
DEFAULT_MEANING = {"D00": "longitudinal crack", "D10": "transverse crack", "D20": "alligator crack", "D40": "pothole"}
DEFAULT_CIVIC = {"D40": ("roads", "pothole"), "D00": ("roads", None), "D10": ("roads", None), "D20": ("roads", None)}


@dataclass
class Detection:
    class_code: str
    label: str
    confidence: float
    box: list[float]                      # x0, y0, x1, y1 in ORIGINAL image pixels
    category: str | None = None
    subcategory: str | None = None

    def as_dict(self) -> dict:
        return {"class_code": self.class_code, "label": self.label, "confidence": round(self.confidence, 4), "box": [round(v, 1) for v in self.box],
                "category": self.category, "subcategory": self.subcategory}


@dataclass
class ImageAnalysis:
    evidence_id: str
    detections: list[Detection] = field(default_factory=list)
    width: int | None = None
    height: int | None = None
    model: str | None = None

    def as_dict(self) -> dict:
        return {"evidence_id": self.evidence_id, "model": self.model, "width": self.width, "height": self.height, "detections": [d.as_dict() for d in self.detections]}


# ------------------------------------------------------------------------------------------------ pure numpy pre/post-processing (unit-tested)
def letterbox(img: np.ndarray, size: int, pad_value: int = 114) -> tuple[np.ndarray, float, tuple[float, float]]:
    """HWC uint8 -> (size,size,3) uint8 with the aspect ratio kept; returns (image, scale, (pad_x, pad_y))."""
    from PIL import Image
    h, w = img.shape[:2]
    r = min(size / h, size / w)
    nh, nw = max(1, round(h * r)), max(1, round(w * r))
    resized = np.asarray(Image.fromarray(img).resize((nw, nh), Image.BILINEAR))
    out = np.full((size, size, 3), pad_value, dtype=np.uint8)
    px, py = (size - nw) // 2, (size - nh) // 2
    out[py:py + nh, px:px + nw] = resized
    return out, r, (float(px), float(py))


def iou_one_to_many(box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    x0, y0 = np.maximum(box[0], boxes[:, 0]), np.maximum(box[1], boxes[:, 1])
    x1, y1 = np.minimum(box[2], boxes[:, 2]), np.minimum(box[3], boxes[:, 3])
    inter = np.clip(x1 - x0, 0, None) * np.clip(y1 - y0, 0, None)
    a = (box[2] - box[0]) * (box[3] - box[1])
    b = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    return inter / np.maximum(a + b - inter, 1e-9)


def nms(boxes: np.ndarray, scores: np.ndarray, iou_thr: float) -> list[int]:
    order, keep = np.argsort(-scores), []
    while order.size:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        rest = order[1:]
        order = rest[iou_one_to_many(boxes[i], boxes[rest]) < iou_thr]
    return keep


def decode_yolov8(raw: np.ndarray, n_classes: int, *, conf: float, iou: float, scale: float, pad: tuple[float, float], orig_wh: tuple[int, int],
                  max_det: int = 50) -> list[tuple[int, float, list[float]]]:
    """Ultralytics ONNX output (1, 4+nc, N) [cx,cy,w,h in letterboxed pixels + class scores] -> [(class_id, score, [x0,y0,x1,y1] in original pixels)]."""
    p = np.asarray(raw)
    if p.ndim == 3:
        p = p[0]
    if p.shape[0] == 4 + n_classes:             # (4+nc, N) -> (N, 4+nc)
        p = p.T
    if p.shape[1] != 4 + n_classes:
        raise ValueError(f"unexpected detector output shape {np.asarray(raw).shape} for {n_classes} classes")
    scores_all = p[:, 4:]
    cls = scores_all.argmax(1)
    sc = scores_all.max(1)
    m = sc >= conf
    if not m.any():
        return []
    p, cls, sc = p[m], cls[m], sc[m]
    cx, cy, w, h = p[:, 0], p[:, 1], p[:, 2], p[:, 3]
    xyxy = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], 1)
    xyxy[:, [0, 2]] = (xyxy[:, [0, 2]] - pad[0]) / scale
    xyxy[:, [1, 3]] = (xyxy[:, [1, 3]] - pad[1]) / scale
    W, H = orig_wh
    xyxy[:, [0, 2]] = np.clip(xyxy[:, [0, 2]], 0, W)
    xyxy[:, [1, 3]] = np.clip(xyxy[:, [1, 3]], 0, H)
    out = []
    for c in np.unique(cls):                   # class-wise NMS
        idx = np.where(cls == c)[0]
        for k in nms(xyxy[idx], sc[idx], iou):
            j = idx[k]
            out.append((int(c), float(sc[j]), [float(v) for v in xyxy[j]]))
    out.sort(key=lambda t: -t[1])
    return out[:max_det]


# ------------------------------------------------------------------------------------------------ the detector
class OnnxRoadDamageDetector:
    """``path`` = a ``.onnx`` file or a directory holding ``best.onnx`` (+ optional ``model_card.json``)."""

    def __init__(self, path: str | Path, *, conf: float = 0.25, iou: float = 0.45, imgsz: int | None = None):
        import onnxruntime as ort
        p = Path(path)
        onnx_path = p if p.suffix == ".onnx" else p / "best.onnx"
        if not onnx_path.is_file():
            raise FileNotFoundError(f"vision model not found: {onnx_path}")
        card_path = onnx_path.parent / "model_card.json"
        card = json.loads(card_path.read_text(encoding="utf-8")) if card_path.is_file() else {}
        self.classes: list[str] = card.get("classes") or DEFAULT_CLASSES
        self.meaning: dict[str, str] = card.get("class_meaning") or DEFAULT_MEANING
        self.civic = {k: tuple(v) for k, v in (card.get("civic_mapping") or DEFAULT_CIVIC).items()}
        self.model_name = f"{card.get('model_name', 'road-damage-yolo')}@{card.get('version', onnx_path.stem)}"
        self.conf, self.iou = conf, iou
        self.session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        inp = self.session.get_inputs()[0]
        shape = inp.shape
        self.imgsz = imgsz or (int(shape[2]) if len(shape) == 4 and isinstance(shape[2], int) else int(card.get("imgsz", 640)))
        self.input_name = inp.name

    def detect(self, image_bytes: bytes, evidence_id: str = "") -> ImageAnalysis:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        arr = np.asarray(img)
        h, w = arr.shape[:2]
        boxed, scale, pad = letterbox(arr, self.imgsz)
        x = (boxed.astype(np.float32) / 255.0).transpose(2, 0, 1)[None]
        raw = self.session.run(None, {self.input_name: x})[0]
        dets = []
        for cid, score, box in decode_yolov8(raw, len(self.classes), conf=self.conf, iou=self.iou, scale=scale, pad=pad, orig_wh=(w, h)):
            code = self.classes[cid]
            cat, sub = self.civic.get(code, (None, None))
            dets.append(Detection(class_code=code, label=self.meaning.get(code, code), confidence=score, box=box, category=cat, subcategory=sub))
        return ImageAnalysis(evidence_id=evidence_id, detections=dets, width=w, height=h, model=self.model_name)


def summarize(analyses: Sequence[ImageAnalysis]) -> dict | None:
    """Strongest civic finding over all images: {category, subcategory, confidence, class_code, evidence_id} or None."""
    best = None
    for a in analyses:
        for d in a.detections:
            if d.category and (best is None or d.confidence > best["confidence"]):
                best = {"category": d.category, "subcategory": d.subcategory, "confidence": d.confidence, "class_code": d.class_code, "label": d.label, "evidence_id": a.evidence_id}
    return best


class LocalVisionAnalyzer:
    """ImageAnalyzer port implementation: runs the detector on IMAGE evidence that carries bytes (a signed URL is never fetched here)."""

    def __init__(self, detector: OnnxRoadDamageDetector):
        self.detector = detector

    def analyze(self, evidence) -> ImageAnalysis | None:
        if getattr(evidence, "media_type", None) != "IMAGE" or not getattr(evidence, "data", None):
            return None
        return self.detector.detect(evidence.data, evidence.evidence_id)


def build_from_env(env: dict | None = None) -> LocalVisionAnalyzer | None:
    """``AI_VISION_ONNX_PATH`` -> analyzer, or None (unset, missing file, or onnxruntime/Pillow not installed: logged, never fatal)."""
    import os
    path = (env or os.environ).get("AI_VISION_ONNX_PATH")
    if not path:
        return None
    try:
        return LocalVisionAnalyzer(OnnxRoadDamageDetector(path))
    except Exception as e:     # optional component: never break startup
        log.error("local vision model not loaded (%s: %s); running without it", type(e).__name__, e)
        return None
