"""Minimal but REAL M6 / M7 ONNX artifacts for backend tests (the production loaders ``OnnxTextClassifier`` / ``OnnxEmbedder`` and onnxruntime run on them).

They are not trained models: the classifier returns constant logits that favour one label; the embedder is a fixed random word-embedding table, mean-pooled and L2-normalised,
so texts that share words get a high cosine similarity (and the dimension can be 384 to exercise the pgvector index). Needs ``onnx``, ``onnxruntime``, ``tokenizers``.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from ai.inference.config import load_taxonomy

SCHEMA = "civic-onnx-text/1"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _tokenizer(path: Path, words: list[str]) -> None:
    from tokenizers import Tokenizer, models, pre_tokenizers
    vocab = {"[PAD]": 0, "[UNK]": 1, **{w: i + 2 for i, w in enumerate(dict.fromkeys(w.lower() for w in words))}}
    tok = Tokenizer(models.WordLevel(vocab, unk_token="[UNK]"))
    tok.pre_tokenizer = pre_tokenizers.Whitespace()
    tok.save(str(path))


def _save(model, path: Path) -> None:
    import onnx
    onnx.checker.check_model(model)
    onnx.save(model, str(path))


def write_m6_artifact(out: Path, *, favour: str = "roads/pothole", strength: float = 8.0, version: str = "test-1") -> Path:
    """Classifier whose logits always favour ``favour`` by ``strength`` (a softmax with temperature 1 then gives it a probability near 1 when strength is large)."""
    from onnx import TensorProto, helper, numpy_helper
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    labels = list(load_taxonomy().label_ids)
    row = np.zeros((1, len(labels)), dtype=np.float32)
    row[0, labels.index(favour)] = strength
    nodes = [helper.make_node("Cast", ["input_ids"], ["ids_f"], to=TensorProto.FLOAT),
             helper.make_node("ReduceMax", ["ids_f"], ["mx"], axes=[1], keepdims=1),
             helper.make_node("Mul", ["mx", "zero"], ["z"]),
             helper.make_node("Add", ["z", "row"], ["logits"])]
    graph = helper.make_graph(nodes, "m6_const", [helper.make_tensor_value_info("input_ids", TensorProto.INT64, ["b", "s"]),
                                                  helper.make_tensor_value_info("attention_mask", TensorProto.INT64, ["b", "s"])],
                              [helper.make_tensor_value_info("logits", TensorProto.FLOAT, ["b", len(labels)])],
                              [numpy_helper.from_array(np.zeros((1, 1), np.float32), "zero"), numpy_helper.from_array(row, "row")])
    _save(helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)], ir_version=8), out / "classifier.onnx")
    _tokenizer(out / "tokenizer.json", ["pothole", "road", "garbage", "water", "light", "the", "a"])
    manifest = {"artifact_schema": SCHEMA, "kind": "classifier", "model_name": "civic-text-m6", "model_version": version, "labels": labels, "max_len": 16, "prefix": "",
                "temperature": 1.0, "pad_token_id": 0, "pad_token": "[PAD]", "files": {"classifier.onnx": _sha(out / "classifier.onnx"), "tokenizer.json": _sha(out / "tokenizer.json")}}
    (out / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return out


def write_m7_artifact(out: Path, *, dim: int = 384, words: list[str] | None = None, version: str = "test-1", seed: int = 7) -> Path:
    """Embedder: ``normalize(mean(table[ids] * mask))`` with a seeded random table over ``words`` (unknown words share one row)."""
    from onnx import TensorProto, helper, numpy_helper
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    vocab = list(dict.fromkeys(w.lower() for w in (words or ["pothole", "road", "school", "market", "garbage", "water", "light", "near", "big", "the", "a", "street", "leak"])))
    _tokenizer(out / "tokenizer.json", vocab)
    table = np.random.default_rng(seed).normal(size=(len(vocab) + 2, dim)).astype(np.float32)
    nodes = [helper.make_node("Gather", ["table", "input_ids"], ["emb"], axis=0),
             helper.make_node("Cast", ["attention_mask"], ["m"], to=TensorProto.FLOAT),
             helper.make_node("Unsqueeze", ["m", "ax2"], ["m3"]),
             helper.make_node("Mul", ["emb", "m3"], ["masked"]),
             helper.make_node("ReduceSum", ["masked", "ax1"], ["sum"], keepdims=0),
             helper.make_node("ReduceSum", ["m", "ax1"], ["cnt"], keepdims=1),
             helper.make_node("Max", ["cnt", "one"], ["cnt1"]),
             helper.make_node("Div", ["sum", "cnt1"], ["mean"]),
             helper.make_node("ReduceL2", ["mean"], ["nrm"], axes=[1], keepdims=1),
             helper.make_node("Max", ["nrm", "eps"], ["nrm1"]),
             helper.make_node("Div", ["mean", "nrm1"], ["embeddings"])]
    inits = [numpy_helper.from_array(table, "table"), numpy_helper.from_array(np.array([2], np.int64), "ax2"), numpy_helper.from_array(np.array([1], np.int64), "ax1"),
             numpy_helper.from_array(np.array([[1.0]], np.float32), "one"), numpy_helper.from_array(np.array([[1e-9]], np.float32), "eps")]
    graph = helper.make_graph(nodes, "m7_mean", [helper.make_tensor_value_info("input_ids", TensorProto.INT64, ["b", "s"]),
                                                 helper.make_tensor_value_info("attention_mask", TensorProto.INT64, ["b", "s"])],
                              [helper.make_tensor_value_info("embeddings", TensorProto.FLOAT, ["b", dim])], inits)
    _save(helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)], ir_version=8), out / "embedder.onnx")
    manifest = {"artifact_schema": SCHEMA, "kind": "embedder", "model_name": "civic-embed-m7", "model_version": version, "max_len": 32, "prefix": "", "dimension": dim,
                "pad_token_id": 0, "pad_token": "[PAD]", "files": {"embedder.onnx": _sha(out / "embedder.onnx"), "tokenizer.json": _sha(out / "tokenizer.json")}}
    (out / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return out
