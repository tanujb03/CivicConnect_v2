"""Notebook 07 end to end on a TINY random encoder and a scripted corpus (CPU, no downloads): data discovery, training, evaluation, ONNX export of M6 + M7, backend runtime check, bundle."""
import json
import zipfile
from pathlib import Path

import nbformat
import pytest

pytest.importorskip("torch")
pytest.importorskip("transformers")
pytest.importorskip("onnxruntime")
pytest.importorskip("onnx")

from ai.training.src.text_corpus import build as cb  # noqa: E402
from ai.training.src.text_corpus import generate as gen  # noqa: E402
from ai.training.src.text_corpus import spec  # noqa: E402
from ai.training.tests.test_text_model_e2e import LabelAware  # noqa: E402
from ai.training.tests.tiny_text_model import build_tiny_encoder  # noqa: E402

NB = Path(__file__).resolve().parents[1] / "notebooks" / "07_text_models_m6_m7_kaggle.ipynb"


@pytest.mark.slow
@pytest.mark.parametrize("num_gpus", ["0", pytest.param("auto", marks=pytest.mark.skipif(not __import__("torch").cuda.is_available(), reason="needs a CUDA GPU"))])
def test_notebook_07_runs_end_to_end_in_smoke_mode_and_writes_both_models(tmp_path, monkeypatch, num_gpus):
    """"0" pins the CPU (deterministic everywhere); "auto" uses whatever GPUs are visible (one on the dev laptop; two on Kaggle T4 x2)."""
    from nbclient import NotebookClient
    cells = spec.build_cells(languages=["en"], styles=["sms_short", "angry", "typo_noisy", "landmark", "voice_transcript", "elderly_simple"], k=12)
    gen.generate_shards(cells, {"en": LabelAware()}, tmp_path / "shards", log=lambda s: None)
    corpus = tmp_path / "corpus"
    cb.build(tmp_path / "shards", corpus, seed=5)
    texts = [json.loads(x)["text"] for n in ("train", "val", "test") for x in (corpus / f"{n}.jsonl").read_text(encoding="utf-8").splitlines()]
    enc = build_tiny_encoder(tmp_path / "enc", texts)
    for k, v in {"CIVIC_WORKDIR": str(tmp_path / "work"), "CIVIC_CORPUS_DIR": str(corpus), "CIVIC_TEXT_MODEL": str(enc), "CIVIC_TEXT_PREFIX": "", "CIVIC_TEXT_VERSION": "ci", "CIVIC_NUM_GPUS": num_gpus}.items():
        monkeypatch.setenv(k, v)
    nb = nbformat.read(NB, as_version=4)
    NotebookClient(nb, timeout=900, kernel_name="python3", resources={"metadata": {"path": str(NB.parent)}}).execute()
    out = "\n".join(o.get("text", "") for c in nb.cells if c.cell_type == "code" for o in c.get("outputs", []))
    assert "Traceback" not in out and "backend ONNX classifier" in out and "embedder cross-language check" in out and "NO GOLD SET" in out
    assert "GPUs: " in out and "training hardware:" in out and "seconds per epoch:" in out
    if num_gpus == "0":
        assert "GPUs: 0 used" in out and "(CPU:" in out
    z = tmp_path / "work" / "civic_text_models_smoke_ci.zip"
    names = set(zipfile.ZipFile(z).namelist())
    assert {"civic_text_m6/ci/classifier.onnx", "civic_text_m6/ci/manifest.json", "civic_text_m6/ci/tokenizer.json", "civic_embed_m7/ci/embedder.onnx", "civic_embed_m7/ci/manifest.json"} <= names
    m6 = json.loads(zipfile.ZipFile(z).read("civic_text_m6/ci/manifest.json"))
    assert m6["smoke_run"] is True and m6["synthetic_training_data"] is True and "template_unseen_families" in m6["results"] and m6["corpus_manifest"]["leakage_rule"]
    th = m6["training_hardware"]                                    # new keys only: the backend reads the same manifest
    assert th["world_size"] >= 1 and th["batch_effective"] == 32 and th["batch_per_gpu"] <= 32 and th["wall_seconds"] > 0 and (th["gpu_count"] == 0) == (num_gpus == "0")
    assert json.loads(zipfile.ZipFile(z).read("civic_embed_m7/ci/manifest.json"))["fine_tuned"] is False
