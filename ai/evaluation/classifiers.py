"""One loader for every local text classifier artifact: the B0 sklearn bundle or an exported M6 ONNX directory (``civic-onnx-text/1``)."""
from __future__ import annotations

import json
from pathlib import Path

from ai.inference.local.text_classifier import LocalTextClassifier

ONNX_SCHEMA = "civic-onnx-text/1"


def is_onnx_artifact(path: Path) -> bool:
    manifest = Path(path) / "manifest.json"
    if not manifest.is_file():
        return False
    try:
        return json.loads(manifest.read_text(encoding="utf-8")).get("artifact_schema") == ONNX_SCHEMA
    except (OSError, ValueError):
        return False


def load_classifier(path: Path | str):
    """Return an object with ``predict(text) -> LocalPrediction`` for either artifact type."""
    path = Path(path)
    if is_onnx_artifact(path):
        from ai.training.src.text_model.runtime import load_backend_text_model
        return load_backend_text_model().OnnxTextClassifier(path)
    return LocalTextClassifier.load(path)
