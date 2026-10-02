"""Local text models in the backend: the fine-tuned multilingual classifier (M6) and the sentence embedder (M7), both ONNX on CPU.

Artifact layout (written by ``ai/training/src/text_model/export.py``): ``manifest.json`` (schema ``civic-onnx-text/1``), ``classifier.onnx`` | ``embedder.onnx`` (+ optional
``classifier.int8.onnx``), ``tokenizer.json``. Checksums are verified at load. Needs ``onnxruntime`` and ``tokenizers`` (both optional backend dependencies).

``OnnxTextClassifier`` is a drop-in for ``ai.inference.local.text_classifier.LocalTextClassifier`` (same ``predict`` / ``model_name`` / ``model_version`` / ``label_ids``), so
``AIService(classifier=...)`` uses it for the offline fallback and the provider cross-check without any change to ``ai/inference``.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path

import numpy as np

from ai.inference.errors import ArtifactError
from ai.inference.local.text_classifier import LocalPrediction

log = logging.getLogger("civicconnect.text_model")
SCHEMA = "civic-onnx-text/1"


class _OnnxText:
    kind = ""
    onnx_names: tuple[str, ...] = ()

    def __init__(self, path: str | Path, *, prefer_int8: bool | None = None, threads: int = 2):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        d = Path(path)
        mf = d / "manifest.json"
        if not mf.is_file():
            raise ArtifactError(f"manifest.json not found in {d}")
        self.manifest = json.loads(mf.read_text(encoding="utf-8"))
        if self.manifest.get("artifact_schema") != SCHEMA or self.manifest.get("kind") != self.kind:
            raise ArtifactError(f"{d} is not a {self.kind} artifact of schema {SCHEMA}")
        for name, expected in self.manifest.get("files", {}).items():
            f = d / name
            if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest() != expected:
                raise ArtifactError(f"artifact file missing or modified: {name}")
        want_int8 = (os.environ.get("AI_TEXT_PREFER_INT8", "1") != "0") if prefer_int8 is None else prefer_int8
        names = [f"{self.kind}.int8.onnx"] * want_int8 + [f"{self.kind}.onnx"]
        model_file = next((d / n for n in names if n in self.manifest["files"]), None)
        if model_file is None:
            raise ArtifactError("no onnx model listed in the manifest")
        self.model_file = model_file.name
        self.max_len = int(self.manifest["max_len"])
        self.prefix = self.manifest.get("prefix", "")
        self.tokenizer = Tokenizer.from_file(str(d / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=self.max_len)
        self.tokenizer.enable_padding(pad_id=int(self.manifest.get("pad_token_id", 0)), pad_token=self.manifest.get("pad_token", "[PAD]"))
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        self.session = ort.InferenceSession(str(model_file), sess_options=so, providers=["CPUExecutionProvider"])

    @property
    def model_name(self) -> str:
        return self.manifest.get("model_name", self.kind)

    @property
    def model_version(self) -> str:
        return str(self.manifest.get("model_version", ""))

    def _run(self, texts: list[str]) -> np.ndarray:
        encs = self.tokenizer.encode_batch([self.prefix + t for t in texts])
        ids = np.array([e.ids for e in encs], dtype=np.int64)
        mask = np.array([e.attention_mask for e in encs], dtype=np.int64)
        return self.session.run(None, {"input_ids": ids, "attention_mask": mask})[0]


class OnnxTextClassifier(_OnnxText):
    kind = "classifier"

    def __init__(self, path: str | Path, **kw):
        super().__init__(path, **kw)
        self.label_ids: list[str] = list(self.manifest["labels"])
        self.temperature = float(self.manifest.get("temperature", 1.0))
        self._cat_index: dict[str, list[int]] = {}
        for i, lid in enumerate(self.label_ids):
            self._cat_index.setdefault(lid.split("/", 1)[0], []).append(i)

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        z = self._run(texts).astype(np.float64) / self.temperature
        z -= z.max(axis=1, keepdims=True)
        e = np.exp(z)
        return e / e.sum(axis=1, keepdims=True)

    def predict(self, text: str, top_k: int = 3, explain_k: int = 5) -> LocalPrediction:   # noqa: ARG002 (explain_k kept for interface parity)
        if not text.strip():
            return LocalPrediction(label_id="other/unclassified", category="other", subcategory="unclassified", category_probability=0.0, subcategory_probability=0.0, top_k=[],
                                   explanation_terms=[], abstained=True, model_name=self.model_name, model_version=self.model_version)
        probs = self.predict_proba([text])[0]
        order = np.argsort(-probs, kind="stable")
        best = int(order[0])
        cat, _, sub = self.label_ids[best].partition("/")
        return LocalPrediction(label_id=self.label_ids[best], category=cat, subcategory=sub, category_probability=float(sum(probs[i] for i in self._cat_index[cat])),
                               subcategory_probability=float(probs[best]), top_k=[(self.label_ids[int(i)], float(probs[int(i)])) for i in order[:top_k]], explanation_terms=[],
                               abstained=False, model_name=self.model_name, model_version=self.model_version)


class OnnxEmbedder(_OnnxText):
    kind = "embedder"

    @property
    def dimension(self) -> int:
        return int(self.manifest.get("dimension", 0))

    @property
    def tag(self) -> str:
        return f"{self.model_name}@{self.model_version}"

    def embed(self, texts: list[str], batch: int = 32) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), batch):
            out += [list(map(float, row)) for row in self._run([t or "" for t in texts[i:i + batch]])]
        return out


def build_from_env(env: dict | None = None) -> tuple[OnnxTextClassifier | None, OnnxEmbedder | None]:
    """``AI_TEXT_ONNX_PATH`` / ``AI_EMBED_ONNX_PATH`` -> models, or None for each that is unset or fails to load (logged, never fatal)."""
    e = env if env is not None else os.environ
    out: list = []
    for var, cls in (("AI_TEXT_ONNX_PATH", OnnxTextClassifier), ("AI_EMBED_ONNX_PATH", OnnxEmbedder)):
        path = e.get(var)
        model = None
        if path:
            try:
                model = cls(path)
            except Exception as ex:           # optional components
                log.error("%s not loaded (%s: %s)", var, type(ex).__name__, ex)
        out.append(model)
    return out[0], out[1]
