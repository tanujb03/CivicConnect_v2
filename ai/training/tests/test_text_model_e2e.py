"""M6 / M7 pipeline end to end on a TINY random-weight encoder (CPU, no downloads): corpus -> fine-tune -> ONNX export -> backend runtime -> gateway fusion/intake.

Metrics mean nothing here (the corpus is a scripted fake); this proves the plumbing, the tokenizer/ONNX/torch parity and the drop-in classifier contract."""
import json
import re
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("torch")
pytest.importorskip("transformers")
pytest.importorskip("tokenizers")
pytest.importorskip("onnxruntime")
pytest.importorskip("onnx")

from ai.inference.local.text_classifier import LocalPrediction  # noqa: E402
from ai.inference.provider import StructuredResult  # noqa: E402
from ai.training.src.text_corpus import build as cb  # noqa: E402
from ai.training.src.text_corpus import generate as gen  # noqa: E402
from ai.training.src.text_corpus import spec  # noqa: E402
from ai.training.src.text_model import export as ex  # noqa: E402
from ai.training.src.text_model import train as tr  # noqa: E402
from ai.training.tests.tiny_text_model import build_tiny_encoder  # noqa: E402


class LabelAware:
    """Scripted writer whose texts contain the label words, so even a tiny random encoder can learn something."""
    name = "fake"

    def structured_completion(self, *, task, instructions, parts, schema_name, json_schema):
        label = re.search(r"issue: (.+?)(?: \(Hindi|\n)", parts[0].text).group(1)
        style = re.search(r"Style: (.+)", parts[0].text).group(1)[:24]
        return StructuredResult(data={"items": [{"text": f"{label.lower()} complaint, {style}, number {i} near the market"} for i in range(12)]}, model="fake")


@pytest.fixture(scope="module")
def pipeline(tmp_path_factory):
    d = tmp_path_factory.mktemp("m6")
    cells = spec.build_cells(languages=["en"], styles=["sms_short", "angry", "typo_noisy", "landmark", "voice_transcript", "elderly_simple"], k=12)
    gen.generate_shards(cells, {"en": LabelAware()}, d / "shards")
    corpus = d / "corpus"
    cb.build(d / "shards", corpus, seed=5)
    texts = [json.loads(x)["text"] for n in ("train", "val", "test") for x in (corpus / f"{n}.jsonl").read_text(encoding="utf-8").splitlines()]
    enc_dir = build_tiny_encoder(d / "enc", texts)
    model, tok, info = tr.train(corpus, str(enc_dir), epochs=6, batch=32, lr=1e-3, head_lr=3e-3, max_len=32, device="cpu", prefix="", patience=6, log=lambda s: None)
    art = ex.export_classifier(model, tok, info, d / "m6", version="test", sample_texts=[json.loads(x)["text"] for x in (corpus / "test.jsonl").read_text(encoding="utf-8").splitlines()[:40]], quantize=True)
    emb = ex.export_embedder(str(enc_dir), tok, d / "m7", version="test", prefix="", max_len=32, sample_texts=texts[:10])
    return {"art": art, "emb": emb, "info": info, "corpus": corpus, "tok": tok, "model": model}


def test_training_learns_and_reports_every_evaluation_set(pipeline):
    r = pipeline["info"]["results"]
    assert {"val", "test_llm_groups"} <= set(r) and r["val"]["subcategory_accuracy"] > 0.3 and pipeline["info"]["temperature"] > 0 and len(pipeline["info"]["labels"]) == 27
    assert r["test_llm_groups"]["by_language"]["en"]["n"] > 0


def test_onnx_export_matches_torch_and_ships_a_verified_manifest(pipeline):
    m = json.loads((pipeline["art"] / "manifest.json").read_text(encoding="utf-8"))
    assert m["artifact_schema"] == "civic-onnx-text/1" and m["kind"] == "classifier" and m["torch_onnx_parity"]["max_abs_logit_diff"] < 1e-3 and m["torch_onnx_parity"]["argmax_agreement"] == 1.0
    assert "classifier.onnx" in m["files"] and m["synthetic_training_data"] is True and len(m["labels"]) == 27
    assert m["int8"]["agreement_with_fp32"] >= 0 and ("classifier.int8.onnx" in m["files"]) == ("rejected" not in m["int8"])
    e = json.loads((pipeline["emb"] / "manifest.json").read_text(encoding="utf-8"))
    assert e["kind"] == "embedder" and e["torch_onnx_parity"]["max_abs_diff"] < 1e-3 and e["dimension"] == 48


def test_backend_runtime_is_a_drop_in_for_the_local_classifier_contract(pipeline):
    from backend.ai_gateway.text_model import OnnxEmbedder, OnnxTextClassifier
    clf = OnnxTextClassifier(pipeline["art"], prefer_int8=False)
    p = clf.predict("pothole complaint near the market")
    assert isinstance(p, LocalPrediction) and p.label_id == f"{p.category}/{p.subcategory}" and 0 <= p.subcategory_probability <= 1 and p.category_probability >= p.subcategory_probability
    assert len(p.top_k) == 3 and abs(sum(pr for _, pr in clf.predict("x").top_k) - 1) < 1.0 and clf.model_name == "civic-text-m6" and clf.label_ids[0] and clf.model_version == "test"
    assert clf.predict("   ").abstained is True
    probs = clf.predict_proba(["a b c", "another sample"])
    assert probs.shape == (2, 27) and np.allclose(probs.sum(1), 1.0)
    # the exported model reproduces torch on text it has never seen
    import torch
    enc = pipeline["tok"](["pothole complaint near the market"], padding=True, truncation=True, max_length=32, return_tensors="pt")
    with torch.no_grad():
        ref = pipeline["model"](enc["input_ids"], enc["attention_mask"]).numpy()[0] / pipeline["info"]["temperature"]
    ref = np.exp(ref - ref.max())
    ref /= ref.sum()
    assert np.abs(ref - clf.predict_proba(["pothole complaint near the market"])[0]).max() < 1e-3
    q = OnnxTextClassifier(pipeline["art"])                                        # int8 when it agreed with fp32
    assert q.predict("pothole complaint near the market").label_id
    emb = OnnxEmbedder(pipeline["emb"])
    v = np.array(emb.embed(["pothole near school", "pothole near school", "street light is out"]))
    assert v.shape == (3, 48) and np.allclose(np.linalg.norm(v, axis=1), 1.0, atol=1e-4) and np.allclose(v[0], v[1], atol=1e-5) and emb.tag == "civic-embed-m7@test"


def test_tampered_or_wrong_artifacts_are_refused(pipeline, tmp_path):
    import shutil

    from backend.ai_gateway.text_model import OnnxEmbedder, OnnxTextClassifier

    from ai.inference.errors import ArtifactError
    bad = tmp_path / "bad"
    shutil.copytree(pipeline["art"], bad)
    (bad / "tokenizer.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ArtifactError):
        OnnxTextClassifier(bad)
    with pytest.raises(ArtifactError):
        OnnxEmbedder(pipeline["art"])                                              # a classifier is not an embedder
    with pytest.raises(ArtifactError):
        OnnxTextClassifier(tmp_path / "missing")


def test_gateway_uses_the_local_classifier_and_embedder(pipeline, monkeypatch):
    import sys

    from backend.ai_gateway import configure_gateway
    from backend.ai_gateway.deps import build_default_gateway
    from backend.ai_gateway.text_model import build_from_env
    from backend.core.security import create_access_token
    from backend.main import app
    from fastapi.testclient import TestClient

    from ai.inference.service import AIService
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    monkeypatch.setenv("AI_TEXT_ONNX_PATH", str(pipeline["art"]))
    monkeypatch.setenv("AI_EMBED_ONNX_PATH", str(pipeline["emb"]))
    for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "CLOUDFLARE_API_TOKEN", "AI_LOCAL_CLASSIFIER_PATH"):
        monkeypatch.delenv(k, raising=False)
    clf, emb = build_from_env()
    assert clf is not None and emb is not None
    monkeypatch.setattr("backend.ai_gateway.deps.load_env_file", lambda: [])
    gw = build_default_gateway()
    assert isinstance(gw.ai, AIService) and gw.ai.classifier is not None and gw.ai.classifier.model_name == "civic-text-m6" and gw.embedder is not None
    configure_gateway(gw)
    try:
        c = TestClient(app)
        h = {"Authorization": f"Bearer {create_access_token('u1', 'citizen')}"}
        r = c.post("/api/v1/cases/intake/analyze", headers=h, json={"text": "pothole complaint near the market"}).json()
        assert r["ai_metadata"]["source"] == "local_fallback" and r["ai_metadata"]["model"] == "civic-text-m6" and r["alternatives"] and any(w.startswith("LOCAL_FALLBACK_USED") for w in r["warnings"])
        pair = json.loads((Path(__file__).resolve().parents[2] / "evaluation/datasets/demo_city_v1/ground_truth.json").read_text(encoding="utf-8"))["possible_duplicate_pairs"][0]
        f = c.post(f"/api/v1/cases/{pair['case_a']}/fusion/analyze", headers={"Authorization": f"Bearer {create_access_token('u2', 'operator')}"}).json()
        assert f["matches"] and f["matches"][0]["semantic_source"] if "semantic_source" in f["matches"][0] else True
        assert f["ai_metadata"]["model"] == "civic-embed-m7@test" and f["ai_metadata"]["source"] == "provider+rules"
        assert any(w.startswith("FUSION_UNCALIBRATED_PRIOR") for w in f["warnings"])        # embedding weights are not calibrated yet: said out loud
    finally:
        configure_gateway(None)


def test_fusion_calibrator_fits_embedding_weights_with_the_local_embedder(pipeline, tmp_path):
    from ai.training.src import build_dataset
    from ai.training.src import train_fusion_calibrator as tf
    data = tmp_path / "data"
    build_dataset.build(data, seed=42, test_fold=4, n_train=2, n_val=1, n_test=1, pairs_train=200, pairs_val=100, pairs_test=20)
    out = tf.run(data, tmp_path / "fw", semantic_mode="local", embed_onnx=pipeline["emb"])
    doc = json.loads((Path(out) / "fusion_weights.json").read_text(encoding="utf-8"))
    assert doc["semantic_trained_on"] == "embedding" and doc["status"] == "calibrated_synthetic" and doc["semantic"] >= 0
    with pytest.raises(SystemExit):
        tf.run(data, tmp_path / "fw2", semantic_mode="local")


def test_evaluation_harness_loads_onnx_and_b0_artifacts_through_one_loader(pipeline):
    from ai.evaluation import run_eval
    from ai.evaluation.classifiers import is_onnx_artifact, load_classifier
    from ai.inference.local.text_classifier import LocalTextClassifier
    fixture = Path(__file__).resolve().parent / "fixtures"
    b0 = next((p.parent for p in fixture.rglob("manifest.json") if not is_onnx_artifact(p.parent)), None)
    assert is_onnx_artifact(pipeline["art"]) and not is_onnx_artifact(pipeline["art"].parent)
    clf = load_classifier(pipeline["art"])
    assert clf.model_name == "civic-text-m6" and clf.predict("pothole near the market").label_id
    if b0 is not None:
        assert isinstance(load_classifier(b0), LocalTextClassifier)
    svc, loaded, note = run_eval.build_intake_system("local", pipeline["art"])
    assert svc is not None and loaded is not None and note is None
