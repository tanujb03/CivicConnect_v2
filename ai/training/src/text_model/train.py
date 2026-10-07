"""Fine-tune a multilingual encoder (default: intfloat/multilingual-e5-small) as the 27-way civic classifier (model M6).

Mean-pooled encoder + dropout + linear head. Training uses plain PyTorch (AdamW, warm-up + linear decay, label smoothing, fp16 on CUDA, early stopping on validation
macro-F1) so it runs unchanged on Kaggle, a laptop GPU (RTX 4050, 6 GB) or CPU. ``torch`` / ``transformers`` are imported lazily: the module can be imported (and the data
helpers tested) without them.

Several GPUs (Kaggle T4 x2): ``torch.nn.DataParallel``. The loss is per-sample cross-entropy, computed OUTSIDE the wrapper on the gathered logits, so the gradient is exactly the
single-GPU one; batches come from the same seeded permutation, early stopping / checkpoints / export stay in one process, and the returned model is the unwrapped module.
``batch`` is the EFFECTIVE batch per optimizer step; ``grad_accum`` > 1 splits each step into weighted micro-batches (same gradient, 1/grad_accum of the memory).

Evaluation sets: ``val`` and ``test`` (LLM-written, group-safe), the ORIGINAL template eval set (unseen template families, comparable with B0) and the gold set, reported as one block per provenance (``gold[human, n=..]``, ``gold[llm_authored_claude, n=..]``,
``gold[unspecified, n=..]``; see ``ai.evaluation.gold``).
"""
from __future__ import annotations

import json
import math
import random
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from ai.evaluation.gold import block_meta, split_by_provenance
from ai.inference.config import load_taxonomy
from ai.training.src import hardware as hw

E5_PREFIX = "query: "


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def label_ids() -> list[str]:
    return list(load_taxonomy().label_ids)           # the same order B0 uses


def macro_f1(y_true: np.ndarray, y_pred: np.ndarray, k: int) -> float:
    f = []
    for c in range(k):
        tp = int(((y_pred == c) & (y_true == c)).sum())
        fp = int(((y_pred == c) & (y_true != c)).sum())
        fn = int(((y_pred != c) & (y_true == c)).sum())
        d = 2 * tp + fp + fn
        f.append(2 * tp / d if d else 0.0)
    return float(np.mean(f))


def fit_temperature(logits: np.ndarray, y: np.ndarray) -> float:
    best_t, best = 1.0, float("inf")
    for t in np.arange(0.25, 6.01, 0.05):
        z = logits / t
        z = z - z.max(axis=1, keepdims=True)
        nll = -(z - np.log(np.exp(z).sum(axis=1, keepdims=True)))[np.arange(len(y)), y].mean()
        if nll < best:
            best, best_t = nll, float(t)
    return round(best_t, 2)


def metrics(logits: np.ndarray, rows: list[dict], labels: list[str]) -> dict:
    idx = {l: i for i, l in enumerate(labels)}
    y = np.array([idx[r["label_id"]] for r in rows])
    pred = logits.argmax(1)
    cat = lambda i: labels[i].split("/")[0]                      # noqa: E731
    by_lang: dict[str, list[bool]] = defaultdict(list)
    for r, p, t in zip(rows, pred, y):
        by_lang[r["language"]].append(bool(p == t))
    return {"n": len(rows), "subcategory_accuracy": round(float((pred == y).mean()), 4), "category_accuracy": round(float(np.mean([cat(p) == cat(t) for p, t in zip(pred, y)])), 4),
            "macro_f1": round(macro_f1(y, pred, len(labels)), 4), "by_language": {k: {"n": len(v), "subcategory_accuracy": round(float(np.mean(v)), 4)} for k, v in sorted(by_lang.items())}}


def template_eval_rows(path: Path) -> list[dict]:
    return [{"text": r["text"], "language": r["language"], "label_id": f"{r['category']}/{r['subcategory']}"} for r in read_jsonl(path)]


def evaluation_sets(data: dict[str, list[dict]], gold: list[dict]) -> tuple[dict[str, list[dict]], set[str]]:
    """The named sets to score, and which names are gold. Gold is split by provenance into ``gold[<provenance>, n=<rows>]`` blocks: never pooled, never called human unless marked human."""
    gold_sets = split_by_provenance(gold)
    return {"val": data["val"], "test_llm_groups": data["test"], **gold_sets}, set(gold_sets)


def block_result(logits: np.ndarray, rows: list[dict], labels: list[str], *, gold: bool) -> dict:
    """Metrics of one evaluation set; a gold block also carries its provenance, whether it is human-written, and what may (not) be claimed from it."""
    m = metrics(logits, rows, labels)
    return {**m, **block_meta(rows)} if gold else m


# ------------------------------------------------------------------------------------------------ torch part
def build_model(model_name: str, n_labels: int, dropout: float = 0.1):
    import torch
    from transformers import AutoModel

    class Classifier(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.encoder = AutoModel.from_pretrained(model_name)
            self.drop = torch.nn.Dropout(dropout)
            self.head = torch.nn.Linear(self.encoder.config.hidden_size, n_labels)

        def pooled(self, input_ids, attention_mask):
            h = self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
            m = attention_mask.unsqueeze(-1).to(h.dtype)
            return (h * m).sum(1) / m.sum(1).clamp(min=1e-9)

        def forward(self, input_ids, attention_mask):
            return self.head(self.drop(self.pooled(input_ids, attention_mask)))

    return Classifier()


def micro_batches(sel: np.ndarray, grad_accum: int) -> list[np.ndarray]:
    """Split one optimizer step's indices into at most ``grad_accum`` non-empty micro-batches (sizes differ by at most one)."""
    return [c for c in np.array_split(sel, max(1, min(int(grad_accum), len(sel)))) if len(c)]


def resolve_devices(device: str | None, num_gpus: int | None, device_ids: list[int] | None = None) -> tuple[str, list[int]]:
    """(device, GPU ids to use). ``num_gpus`` None = every visible GPU, 0 = CPU. An explicit ``device_ids`` wins (tests use [0, 0] to run two replicas on one GPU)."""
    import torch
    if device_ids is not None:
        return device or "cuda", list(device_ids)
    avail = torch.cuda.device_count() if torch.cuda.is_available() else 0
    if device is None:
        device = "cuda" if avail and num_gpus != 0 else "cpu"
    if not str(device).startswith("cuda"):
        return "cpu", []
    if ":" in str(device):                                       # an explicit single GPU, e.g. "cuda:1"
        return str(device), [int(str(device).split(":")[1])]
    return "cuda", list(range(max(1, avail if num_gpus is None else min(num_gpus, avail))))


def _batches(tokenizer, texts: list[str], max_len: int, batch: int, prefix: str):
    for i in range(0, len(texts), batch):
        enc = tokenizer([prefix + t for t in texts[i:i + batch]], padding=True, truncation=True, max_length=max_len, return_tensors="pt")
        yield i, enc["input_ids"], enc["attention_mask"]


def predict_logits(model, tokenizer, texts: list[str], *, max_len: int, batch: int, prefix: str, device: str) -> np.ndarray:
    import torch
    model.eval()
    out = []
    with torch.no_grad():
        for _, ids, mask in _batches(tokenizer, texts, max_len, batch, prefix):
            out.append(model(ids.to(device), mask.to(device)).float().cpu().numpy())
    return np.concatenate(out) if out else np.zeros((0, 0))


def train(corpus_dir: Path, model_name: str, *, epochs: int = 5, batch: int = 32, lr: float = 3e-5, head_lr: float = 1e-3, max_len: int = 64, seed: int = 42, device: str | None = None,
          prefix: str = E5_PREFIX, patience: int = 2, label_smoothing: float = 0.05, template_eval: Path | None = None, log=print,
          num_gpus: int | None = None, grad_accum: int = 1, device_ids: list[int] | None = None):
    """Returns (model, tokenizer, info). ``info`` holds the metrics of every evaluation set, the fitted temperature, the label list and ``hardware`` (what the run used).

    ``batch`` = effective batch per optimizer step. ``num_gpus``: None = all visible GPUs, 1 = single GPU, 0 = CPU. ``grad_accum`` splits every step into that many micro-batches."""
    import torch
    from transformers import AutoTokenizer

    t_start = time.perf_counter()
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)                       # seeds every visible CUDA device too
    device, ids = resolve_devices(device, num_gpus, device_ids)
    cuda = device.startswith("cuda")
    grad_accum = max(1, int(grad_accum))
    shares = hw.split_batch(math.ceil(batch / grad_accum), len(ids), must_divide=False)
    labels = label_ids()
    idx = {l: i for i, l in enumerate(labels)}
    data = {n: read_jsonl(corpus_dir / f"{n}.jsonl") for n in ("train", "val", "test")}
    gold = read_jsonl(corpus_dir / "gold.jsonl") if (corpus_dir / "gold.jsonl").exists() else []
    tok = AutoTokenizer.from_pretrained(model_name)
    model = build_model(model_name, len(labels)).to(device)
    net = torch.nn.DataParallel(model, device_ids=ids, output_device=ids[0]) if len(ids) > 1 else model        # forward only; everything else uses the unwrapped `model`
    log(f"M6 training on {f'{len(ids)} GPU(s)' if ids else 'the CPU'} ({'DataParallel' if len(ids) > 1 else 'single device'}): effective batch {batch}"
        + (f" = {grad_accum} micro-batches of {shares.effective}" if grad_accum > 1 else "") + (f", at most {shares.per_gpu} samples per GPU per forward" if ids else "") + f", device {device}")
    y_tr = np.array([idx[r["label_id"]] for r in data["train"]])
    steps = epochs * math.ceil(len(y_tr) / batch)
    opt = torch.optim.AdamW([{"params": model.encoder.parameters(), "lr": lr}, {"params": model.head.parameters(), "lr": head_lr}], weight_decay=0.01)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min((s + 1) / max(1, int(0.06 * steps)), max(0.0, (steps - s) / max(1, steps - int(0.06 * steps)))))
    scaler = torch.amp.GradScaler("cuda", enabled=cuda)
    loss_fn = torch.nn.CrossEntropyLoss(label_smoothing=label_smoothing)
    best, best_state, bad, history = -1.0, None, 0, []
    texts_tr = [r["text"] for r in data["train"]]
    epoch_seconds: list[float] = []
    for ep in range(epochs):
        t_ep = time.perf_counter()
        model.train()
        order = np.random.permutation(len(texts_tr))
        total = 0.0
        for i in range(0, len(order), batch):
            sel = order[i:i + batch]
            opt.zero_grad(set_to_none=True)
            step_loss = 0.0
            for part in micro_batches(sel, grad_accum):                  # one micro-batch when grad_accum == 1
                enc = tok([prefix + texts_tr[j] for j in part], padding=True, truncation=True, max_length=max_len, return_tensors="pt")
                with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=cuda):
                    logits = net(enc["input_ids"].to(device), enc["attention_mask"].to(device))          # DataParallel scatters / gathers; the loss is NOT inside it
                    loss = loss_fn(logits, torch.as_tensor(y_tr[part], device=logits.device)) * (len(part) / len(sel))
                scaler.scale(loss).backward()
                step_loss += float(loss)
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            sched.step()
            total += step_loss * len(sel)
        vl = predict_logits(net, tok, [r["text"] for r in data["val"]], max_len=max_len, batch=128, prefix=prefix, device=device)
        vm = metrics(vl, data["val"], labels)
        epoch_seconds.append(round(time.perf_counter() - t_ep, 2))
        history.append({"epoch": ep + 1, "train_loss": round(total / len(order), 4), "val_macro_f1": vm["macro_f1"], "val_subcategory_accuracy": vm["subcategory_accuracy"],
                        "seconds": epoch_seconds[-1]})
        log(f"epoch {ep + 1}/{epochs}: train loss {history[-1]['train_loss']}  val macro-F1 {vm['macro_f1']}  val subcat acc {vm['subcategory_accuracy']}  ({epoch_seconds[-1]}s)")
        if vm["macro_f1"] > best + 1e-4:
            best, bad = vm["macro_f1"], 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad > patience:
                log("early stop")
                break
    model.load_state_dict(best_state)
    results = {}
    val_logits = predict_logits(net, tok, [r["text"] for r in data["val"]], max_len=max_len, batch=128, prefix=prefix, device=device)
    temperature = fit_temperature(val_logits, np.array([idx[r["label_id"]] for r in data["val"]]))
    sets, gold_names = evaluation_sets(data, gold)
    if template_eval and Path(template_eval).exists():
        sets["template_unseen_families"] = template_eval_rows(template_eval)
    for name, rows in sets.items():
        if rows:
            results[name] = block_result(predict_logits(net, tok, [r["text"] for r in rows], max_len=max_len, batch=128, prefix=prefix, device=device), rows, labels, gold=name in gold_names)
            log(f"{name:26s} n={results[name]['n']:5d}  subcategory acc {results[name]['subcategory_accuracy']}  category acc {results[name]['category_accuracy']}  macro-F1 {results[name]['macro_f1']}")
    info = {"labels": labels, "temperature": temperature, "max_len": max_len, "prefix": prefix, "model_name": model_name, "history": history, "results": results,
            "hyperparameters": {"epochs": epochs, "batch": batch, "lr": lr, "head_lr": head_lr, "label_smoothing": label_smoothing, "seed": seed, "device": device,
                                "grad_accum": grad_accum, "num_gpus": len(ids)}}
    info["hardware"] = hw.TrainingHardware(
        gpu_count=len(ids), world_size=max(len(ids), 1), gpu_names=[torch.cuda.get_device_name(i) for i in ids], parallel="DataParallel" if len(ids) > 1 else "none",
        batch_effective=batch, batch_per_gpu=shares.per_gpu, grad_accum=grad_accum, wall_seconds=round(time.perf_counter() - t_start, 2), epoch_seconds=epoch_seconds,
        note="" if len(ids) < 2 else "loss computed outside DataParallel on gathered logits; checkpoint and ONNX export come from the unwrapped module").as_dict()
    return model.cpu(), tok, info
