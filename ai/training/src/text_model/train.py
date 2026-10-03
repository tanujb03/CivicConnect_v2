"""Fine-tune a multilingual encoder (default: intfloat/multilingual-e5-small) as the 27-way civic classifier (model M6).

Mean-pooled encoder + dropout + linear head. Training uses plain PyTorch (AdamW, warm-up + linear decay, label smoothing, fp16 on CUDA, early stopping on validation
macro-F1) so it runs unchanged on Kaggle, a laptop GPU (RTX 4050, 6 GB) or CPU. ``torch`` / ``transformers`` are imported lazily: the module can be imported (and the data
helpers tested) without them.

Evaluation sets: ``val`` and ``test`` (LLM-written, group-safe), the ORIGINAL template eval set (unseen template families, comparable with B0) and the team's ``gold`` set.
"""
from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from pathlib import Path

import numpy as np

from ai.inference.config import load_taxonomy

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
          prefix: str = E5_PREFIX, patience: int = 2, label_smoothing: float = 0.05, template_eval: Path | None = None, log=print):
    """Returns (model, tokenizer, info). ``info`` holds the metrics of every evaluation set, the fitted temperature and the label list."""
    import torch
    from transformers import AutoTokenizer

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    labels = label_ids()
    idx = {l: i for i, l in enumerate(labels)}
    data = {n: read_jsonl(corpus_dir / f"{n}.jsonl") for n in ("train", "val", "test")}
    gold = read_jsonl(corpus_dir / "gold.jsonl") if (corpus_dir / "gold.jsonl").exists() else []
    tok = AutoTokenizer.from_pretrained(model_name)
    model = build_model(model_name, len(labels)).to(device)
    y_tr = np.array([idx[r["label_id"]] for r in data["train"]])
    steps = epochs * math.ceil(len(y_tr) / batch)
    opt = torch.optim.AdamW([{"params": model.encoder.parameters(), "lr": lr}, {"params": model.head.parameters(), "lr": head_lr}], weight_decay=0.01)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min((s + 1) / max(1, int(0.06 * steps)), max(0.0, (steps - s) / max(1, steps - int(0.06 * steps)))))
    scaler = torch.amp.GradScaler("cuda", enabled=device == "cuda")
    loss_fn = torch.nn.CrossEntropyLoss(label_smoothing=label_smoothing)
    best, best_state, bad, history = -1.0, None, 0, []
    texts_tr = [r["text"] for r in data["train"]]
    for ep in range(epochs):
        model.train()
        order = np.random.permutation(len(texts_tr))
        total = 0.0
        for i in range(0, len(order), batch):
            sel = order[i:i + batch]
            enc = tok([prefix + texts_tr[j] for j in sel], padding=True, truncation=True, max_length=max_len, return_tensors="pt")
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=device == "cuda"):
                loss = loss_fn(model(enc["input_ids"].to(device), enc["attention_mask"].to(device)), torch.tensor(y_tr[sel]).to(device))
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            sched.step()
            total += float(loss) * len(sel)
        vl = predict_logits(model, tok, [r["text"] for r in data["val"]], max_len=max_len, batch=128, prefix=prefix, device=device)
        vm = metrics(vl, data["val"], labels)
        history.append({"epoch": ep + 1, "train_loss": round(total / len(order), 4), "val_macro_f1": vm["macro_f1"], "val_subcategory_accuracy": vm["subcategory_accuracy"]})
        log(f"epoch {ep + 1}/{epochs}: train loss {history[-1]['train_loss']}  val macro-F1 {vm['macro_f1']}  val subcat acc {vm['subcategory_accuracy']}")
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
    val_logits = predict_logits(model, tok, [r["text"] for r in data["val"]], max_len=max_len, batch=128, prefix=prefix, device=device)
    temperature = fit_temperature(val_logits, np.array([idx[r["label_id"]] for r in data["val"]]))
    sets = {"val": data["val"], "test_llm_groups": data["test"], "gold": gold}
    if template_eval and Path(template_eval).exists():
        sets["template_unseen_families"] = template_eval_rows(template_eval)
    for name, rows in sets.items():
        if rows:
            results[name] = metrics(predict_logits(model, tok, [r["text"] for r in rows], max_len=max_len, batch=128, prefix=prefix, device=device), rows, labels)
            log(f"{name:26s} n={results[name]['n']:5d}  subcategory acc {results[name]['subcategory_accuracy']}  category acc {results[name]['category_accuracy']}  macro-F1 {results[name]['macro_f1']}")
    info = {"labels": labels, "temperature": temperature, "max_len": max_len, "prefix": prefix, "model_name": model_name, "history": history, "results": results,
            "hyperparameters": {"epochs": epochs, "batch": batch, "lr": lr, "head_lr": head_lr, "label_smoothing": label_smoothing, "seed": seed, "device": device}}
    return model.cpu(), tok, info
