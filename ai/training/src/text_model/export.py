"""Export M6 (classifier) and M7 (embedder) to ONNX + tokenizer.json + manifest for the backend (CPU inference; see ``backend/ai_gateway/text_model.py``)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

SCHEMA = "civic-onnx-text/1"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _save_tokenizer(tok, out: Path) -> dict:
    """The fast tokenizer's backend JSON (loaded at inference by the ``tokenizers`` library) + the ids the runtime needs for padding."""
    tok.backend_tokenizer.save(str(out / "tokenizer.json"))
    return {"pad_token_id": int(tok.pad_token_id if tok.pad_token_id is not None else 0), "pad_token": tok.pad_token or "[PAD]"}


def _export(module, tok, path: Path, input_names, output_name: str, max_len: int, opset: int = 17) -> None:
    import torch
    module.eval()
    enc = tok(["civic export sample", "another sample text for the dummy batch"], padding="max_length", truncation=True, max_length=max_len, return_tensors="pt")
    args = (enc["input_ids"], enc["attention_mask"])
    with torch.no_grad():
        torch.onnx.export(module, args, str(path), input_names=input_names, output_names=[output_name], opset_version=opset, dynamo=False,
                          dynamic_axes={input_names[0]: {0: "batch", 1: "seq"}, input_names[1]: {0: "batch", 1: "seq"}, output_name: {0: "batch"}})


def quantize_int8(src: Path, dst: Path) -> None:
    from onnxruntime.quantization import QuantType, quantize_dynamic
    quantize_dynamic(str(src), str(dst), weight_type=QuantType.QInt8)


def _agreement(a: Path, b: Path, tok, texts: list[str], prefix: str, max_len: int) -> float:
    import onnxruntime as ort
    sa, sb = (ort.InferenceSession(str(p), providers=["CPUExecutionProvider"]) for p in (a, b))
    enc = tok([prefix + t for t in texts], padding=True, truncation=True, max_length=max_len, return_tensors="np")
    feed = {"input_ids": enc["input_ids"].astype(np.int64), "attention_mask": enc["attention_mask"].astype(np.int64)}
    return float((sa.run(None, feed)[0].argmax(1) == sb.run(None, feed)[0].argmax(1)).mean())


def export_classifier(model, tok, info: dict, out_dir: Path, *, version: str, sample_texts: list[str], quantize: bool = True, extra: dict | None = None) -> Path:
    """``model`` is the trained ``Classifier`` module. Writes classifier.onnx (+ classifier.int8.onnx when it agrees with fp32 on >= 99% of the sample), tokenizer.json, manifest.json."""
    import onnxruntime as ort
    import torch
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tokinfo = _save_tokenizer(tok, out)
    _export(model, tok, out / "classifier.onnx", ["input_ids", "attention_mask"], "logits", info["max_len"])
    files = {"classifier.onnx": _sha(out / "classifier.onnx"), "tokenizer.json": _sha(out / "tokenizer.json")}
    # parity with torch on a sample
    enc = tok([info["prefix"] + t for t in sample_texts], padding=True, truncation=True, max_length=info["max_len"], return_tensors="pt")
    with torch.no_grad():
        ref = model(enc["input_ids"], enc["attention_mask"]).numpy()
    got = ort.InferenceSession(str(out / "classifier.onnx"), providers=["CPUExecutionProvider"]).run(None, {"input_ids": enc["input_ids"].numpy(), "attention_mask": enc["attention_mask"].numpy()})[0]
    parity = {"max_abs_logit_diff": float(np.abs(ref - got).max()), "argmax_agreement": float((ref.argmax(1) == got.argmax(1)).mean()), "n": len(sample_texts)}
    int8 = None
    if quantize:
        quantize_int8(out / "classifier.onnx", out / "classifier.int8.onnx")
        agree = _agreement(out / "classifier.onnx", out / "classifier.int8.onnx", tok, sample_texts, info["prefix"], info["max_len"])
        if agree >= 0.99:
            files["classifier.int8.onnx"] = _sha(out / "classifier.int8.onnx")
            int8 = {"agreement_with_fp32": round(agree, 4)}
        else:
            (out / "classifier.int8.onnx").unlink()
            int8 = {"agreement_with_fp32": round(agree, 4), "rejected": "below 0.99: fp32 only"}
    manifest = {"artifact_schema": SCHEMA, "kind": "classifier", "model_name": "civic-text-m6", "model_version": version, "base_model": info["model_name"], "labels": info["labels"],
                "max_len": info["max_len"], "prefix": info["prefix"], "temperature": info["temperature"], **tokinfo, "inputs": ["input_ids", "attention_mask"], "output": "logits",
                "files": files, "torch_onnx_parity": parity, "int8": int8, "results": info["results"], "history": info["history"], "hyperparameters": info["hyperparameters"],
                "synthetic_training_data": True, **(extra or {})}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return out


def export_embedder(model_name_or_dir: str, tok, out_dir: Path, *, version: str, prefix: str = "query: ", max_len: int = 128, sample_texts: list[str] | None = None) -> Path:
    """M7: the ORIGINAL pretrained encoder (not fine-tuned) + mean pooling + L2 normalisation -> sentence embeddings."""
    import torch
    from transformers import AutoModel
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    enc_model = AutoModel.from_pretrained(model_name_or_dir)

    class Embedder(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.encoder = enc_model

        def forward(self, input_ids, attention_mask):
            h = self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
            m = attention_mask.unsqueeze(-1).to(h.dtype)
            e = (h * m).sum(1) / m.sum(1).clamp(min=1e-9)
            return torch.nn.functional.normalize(e, dim=-1)

    emb = Embedder().eval()
    tokinfo = _save_tokenizer(tok, out)
    _export(emb, tok, out / "embedder.onnx", ["input_ids", "attention_mask"], "embeddings", max_len)
    files = {"embedder.onnx": _sha(out / "embedder.onnx"), "tokenizer.json": _sha(out / "tokenizer.json")}
    parity = None
    if sample_texts:
        import onnxruntime as ort
        enc = tok([prefix + t for t in sample_texts], padding=True, truncation=True, max_length=max_len, return_tensors="pt")
        with torch.no_grad():
            ref = emb(enc["input_ids"], enc["attention_mask"]).numpy()
        got = ort.InferenceSession(str(out / "embedder.onnx"), providers=["CPUExecutionProvider"]).run(None, {"input_ids": enc["input_ids"].numpy(), "attention_mask": enc["attention_mask"].numpy()})[0]
        parity = {"max_abs_diff": float(np.abs(ref - got).max()), "n": len(sample_texts)}
    manifest = {"artifact_schema": SCHEMA, "kind": "embedder", "model_name": "civic-embed-m7", "model_version": version, "base_model": str(model_name_or_dir), "prefix": prefix, "max_len": max_len,
                "dimension": int(enc_model.config.hidden_size), **tokinfo, "inputs": ["input_ids", "attention_mask"], "output": "embeddings", "files": files, "torch_onnx_parity": parity}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return out
