"""Load the backend's ONNX text-model runtime by file path (it needs only numpy / onnxruntime / tokenizers + ai.inference, not the FastAPI stack)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def load_backend_text_model(repo: Path | None = None):
    path = Path(repo or REPO) / "backend" / "ai_gateway" / "text_model.py"
    spec = importlib.util.spec_from_file_location("civic_text_model", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["civic_text_model"] = mod
    spec.loader.exec_module(mod)
    return mod
