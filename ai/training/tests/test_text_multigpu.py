"""M6 trainer: multi-GPU (DataParallel) and gradient-accumulation behaviour.

CPU tests prove the arithmetic, the loss equivalence and the manifest; the CUDA tests run TWO replicas on the single local GPU (``device_ids=[0, 0]``) to exercise scatter /
replicate / gather / autocast propagation. Real GPU-to-GPU transfer over PCIe can only be verified on a machine with two GPUs (Kaggle T4 x2)."""
import json

import numpy as np
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("transformers")
pytest.importorskip("tokenizers")
pytest.importorskip("onnxruntime")
pytest.importorskip("onnx")

from ai.training.src.text_corpus import build as cb  # noqa: E402
from ai.training.src.text_corpus import generate as gen  # noqa: E402
from ai.training.src.text_corpus import spec  # noqa: E402
from ai.training.src.text_model import export as ex  # noqa: E402
from ai.training.src.text_model import train as tr  # noqa: E402
from ai.training.tests.test_text_model_e2e import LabelAware  # noqa: E402
from ai.training.tests.tiny_text_model import build_tiny_encoder  # noqa: E402

needs_cuda = pytest.mark.skipif(not torch.cuda.is_available(), reason="needs a CUDA GPU")


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    d = tmp_path_factory.mktemp("mg")
    gen.generate_shards(spec.build_cells(languages=["en"], styles=["sms_short", "angry", "typo_noisy", "landmark", "voice_transcript", "elderly_simple"], k=12), {"en": LabelAware()}, d / "shards", log=lambda s: None)
    corpus = d / "corpus"
    cb.build(d / "shards", corpus, seed=5)
    texts = [json.loads(x)["text"] for n in ("train", "val", "test") for x in (corpus / f"{n}.jsonl").read_text(encoding="utf-8").splitlines()]
    return {"corpus": corpus, "enc": str(build_tiny_encoder(d / "enc", texts)), "dir": d}


def run(tiny, **kw):
    args = dict(epochs=2, batch=32, lr=1e-3, head_lr=3e-3, max_len=32, prefix="", patience=3, log=lambda s: None)
    return tr.train(tiny["corpus"], tiny["enc"], **{**args, **kw})


# ---------------------------------------------------------------- pure arithmetic
@pytest.mark.parametrize("n,accum", [(32, 1), (32, 2), (32, 3), (7, 4), (3, 8), (1, 2)])
def test_micro_batches_partition_the_step_without_loss_or_overlap(n, accum):
    sel = np.arange(n) * 3
    parts = tr.micro_batches(sel, accum)
    assert 1 <= len(parts) <= accum and np.array_equal(np.concatenate(parts), sel) and all(len(p) for p in parts)
    assert max(map(len, parts)) - min(map(len, parts)) <= 1


def test_size_weighted_micro_batch_loss_equals_the_full_batch_loss():
    g = torch.Generator().manual_seed(0)
    logits, y = torch.randn(33, 27, generator=g), torch.randint(0, 27, (33,), generator=g)
    ce = torch.nn.CrossEntropyLoss(label_smoothing=0.05)
    parts = tr.micro_batches(np.arange(33), 4)
    got = sum(ce(logits[p], y[p]) * (len(p) / 33) for p in parts)
    assert torch.allclose(got, ce(logits, y), atol=1e-6)


@pytest.mark.parametrize("device,num,ids,expect_cuda", [("cpu", None, None, 0), (None, 0, None, 0), ("cuda", 1, None, 1), ("cuda", 2, None, 1), ("cuda", None, None, 1), ("cuda:0", None, None, 1),
                                                        ("cuda", None, [0, 0], 2)])
def test_resolve_devices(device, num, ids, expect_cuda):
    dev, got = tr.resolve_devices(device, num, ids)
    assert len(got) == expect_cuda and (dev == "cpu") == (expect_cuda == 0)


def test_resolve_devices_with_mocked_gpu_counts(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    for avail, num, expected in [(2, None, [0, 1]), (2, 1, [0]), (2, 8, [0, 1]), (4, 2, [0, 1]), (1, None, [0])]:
        monkeypatch.setattr(torch.cuda, "device_count", lambda avail=avail: avail)
        assert tr.resolve_devices(None, num) == ("cuda", expected)
    monkeypatch.setattr(torch.cuda, "device_count", lambda: 2)
    assert tr.resolve_devices(None, 0) == ("cpu", [])
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(torch.cuda, "device_count", lambda: 0)
    assert tr.resolve_devices(None, None) == ("cpu", [])


# ---------------------------------------------------------------- gradients
def grads_of(model, net, enc, y, accum, device="cpu"):
    ce = torch.nn.CrossEntropyLoss(label_smoothing=0.05)
    model.zero_grad(set_to_none=True)
    for part in tr.micro_batches(np.arange(len(y)), accum):
        ids, mask = enc["input_ids"][part].to(device), enc["attention_mask"][part].to(device)
        logits = net(ids, mask)
        (ce(logits, y[part].to(logits.device)) * (len(part) / len(y))).backward()
    return {k: p.grad.detach().cpu().clone() for k, p in model.named_parameters() if p.grad is not None}


def make_batch(tiny, n=12):
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(tiny["enc"])
    rows = tr.read_jsonl(tiny["corpus"] / "train.jsonl")[:n]
    idx = {label: i for i, label in enumerate(tr.label_ids())}
    enc = tok([r["text"] for r in rows], padding=True, truncation=True, max_length=32, return_tensors="pt")
    return enc, torch.tensor([idx[r["label_id"]] for r in rows])


def test_gradient_accumulation_gives_the_full_batch_gradient(tiny):
    model = tr.build_model(tiny["enc"], 27).eval()                          # eval: no dropout, so the comparison is exact
    enc, y = make_batch(tiny)
    full, accum = grads_of(model, model, enc, y, 1), grads_of(model, model, enc, y, 3)
    assert full.keys() == accum.keys() and all(torch.allclose(full[k], accum[k], atol=1e-5, rtol=1e-4) for k in full)


@needs_cuda
def test_two_replicas_on_one_gpu_give_the_single_device_gradient(tiny):
    """DataParallel(device_ids=[0, 0]) scatters the batch to two replica threads and gathers the logits; the loss outside the wrapper must give the single-device gradient."""
    model = tr.build_model(tiny["enc"], 27).cuda().eval()
    enc, y = make_batch(tiny)
    single = grads_of(model, model, enc, y, 1, "cuda")
    dp = torch.nn.DataParallel(model, device_ids=[0, 0], output_device=0)
    multi = grads_of(model, dp, enc, y, 1, "cuda")
    assert all(torch.allclose(single[k], multi[k], atol=2e-4, rtol=1e-3) for k in single)
    extra = multi.keys() - single.keys()           # DataParallel gives parameters outside the forward path (the unused BERT pooler) a ZERO gradient instead of None: harmless
    assert all(k.startswith("encoder.pooler") and not multi[k].any() for k in extra) and single.keys() <= multi.keys()


# ---------------------------------------------------------------- the training loop
def test_cpu_training_with_grad_accumulation_reports_its_hardware_and_exports_once(tiny):
    model, tok, info = run(tiny, device="cpu", grad_accum=2)
    assert not isinstance(model, torch.nn.DataParallel) and not any(k.startswith("module.") for k in model.state_dict())
    h = info["hardware"]
    assert (h["gpu_count"], h["world_size"], h["parallel"], h["batch_effective"], h["batch_per_gpu"], h["grad_accum"]) == (0, 1, "none", 32, 16, 2)
    assert h["wall_seconds"] > 0 and len(h["epoch_seconds"]) == len(info["history"]) and all("seconds" in e for e in info["history"])
    assert info["hyperparameters"]["grad_accum"] == 2 and info["hyperparameters"]["num_gpus"] == 0
    art = ex.export_classifier(model, tok, info, tiny["dir"] / "m6", version="t", sample_texts=["pothole near the school", "no water supply"], quantize=False)
    m = json.loads((art / "manifest.json").read_text(encoding="utf-8"))
    assert m["training_hardware"]["world_size"] == 1 and m["training_hardware"]["batch_effective"] == 32 and m["artifact_schema"] == "civic-onnx-text/1"
    e = json.loads((ex.export_embedder(tiny["enc"], tok, tiny["dir"] / "m7", version="t", prefix="", max_len=32) / "manifest.json").read_text(encoding="utf-8"))
    assert e["fine_tuned"] is False and e["kind"] == "embedder"


def test_cpu_training_is_reproducible_for_a_fixed_seed(tiny):
    a, b = run(tiny, device="cpu", seed=3, epochs=1)[2], run(tiny, device="cpu", seed=3, epochs=1)[2]
    assert [e["train_loss"] for e in a["history"]] == [e["train_loss"] for e in b["history"]] and a["results"]["val"] == b["results"]["val"]


@needs_cuda
def test_data_parallel_training_runs_and_returns_the_unwrapped_cpu_model(tiny):
    model, tok, info = run(tiny, device_ids=[0, 0], grad_accum=2, batch=33)       # 33 does not split evenly over 2 replicas
    h = info["hardware"]
    assert not isinstance(model, torch.nn.DataParallel) and not any(k.startswith("module.") for k in model.state_dict()) and next(model.parameters()).device.type == "cpu"
    assert (h["gpu_count"], h["world_size"], h["parallel"], h["batch_effective"], h["grad_accum"]) == (2, 2, "DataParallel", 33, 2) and h["batch_per_gpu"] == 9
    art = ex.export_classifier(model, tok, info, tiny["dir"] / "m6dp", version="dp", sample_texts=["pothole near the school"], quantize=False)
    assert json.loads((art / "manifest.json").read_text(encoding="utf-8"))["torch_onnx_parity"]["argmax_agreement"] == 1.0


@needs_cuda
def test_single_gpu_still_trains_and_learns(tiny):
    _, _, info = run(tiny, num_gpus=1, epochs=4)
    assert info["hardware"]["gpu_count"] == 1 and info["hardware"]["parallel"] == "none" and info["results"]["val"]["subcategory_accuracy"] > 0.2
