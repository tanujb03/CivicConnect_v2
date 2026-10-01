"""Dependency-light metrics (numpy/stdlib only)."""
from __future__ import annotations

import math
from collections import Counter
from typing import Sequence

import numpy as np


def accuracy(y_true: Sequence, y_pred: Sequence) -> float:
    return float(np.mean([a == b for a, b in zip(y_true, y_pred)])) if len(y_true) else float("nan")


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - m) / d, (c + m) / d)


def per_class_prf(y_true: Sequence[str], y_pred: Sequence[str], labels: Sequence[str]) -> dict[str, dict]:
    out = {}
    for lab in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == lab and p == lab)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != lab and p == lab)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == lab and p != lab)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        out[lab] = {"precision": prec, "recall": rec, "f1": f1, "support": tp + fn}
    return out


def macro_f1(y_true: Sequence[str], y_pred: Sequence[str], labels: Sequence[str]) -> float:
    prf = per_class_prf(y_true, y_pred, labels)
    present = [l for l in labels if prf[l]["support"] > 0]
    return float(np.mean([prf[l]["f1"] for l in present])) if present else float("nan")


def expected_calibration_error(conf: Sequence[float], correct: Sequence[bool], bins: int = 10) -> float:
    conf, correct = np.asarray(conf, dtype=float), np.asarray(correct, dtype=float)
    if len(conf) == 0:
        return float("nan")
    ece = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        m = (conf >= lo) & ((conf < hi) if b < bins - 1 else (conf <= hi))
        if m.any():
            ece += m.mean() * abs(correct[m].mean() - conf[m].mean())
    return float(ece)


def top_confusions(y_true: Sequence[str], y_pred: Sequence[str], k: int = 8) -> list[dict]:
    c = Counter((t, p) for t, p in zip(y_true, y_pred) if t != p)
    return [{"true": t, "pred": p, "count": n} for (t, p), n in c.most_common(k)]


def auc_roc(scores: Sequence[float], y: Sequence[int]) -> float:
    s, y = np.asarray(scores, dtype=float), np.asarray(y)
    order = np.argsort(s, kind="stable")
    ranks = np.empty(len(s))
    ss = s[order]
    i = 0
    while i < len(ss):
        j = i
        while j + 1 < len(ss) and ss[j + 1] == ss[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2 + 1
        i = j + 1
    pos = y == 1
    n1, n0 = int(pos.sum()), int((~pos).sum())
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)) if n1 and n0 else float("nan")


def precision_recall_at(scores: Sequence[float], y: Sequence[int], thr: float) -> dict:
    s, y = np.asarray(scores, dtype=float), np.asarray(y)
    pred = s >= thr
    tp, fp, fn = int((pred & (y == 1)).sum()), int((pred & (y == 0)).sum()), int((~pred & (y == 1)).sum())
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"threshold": thr, "precision": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0,
            "tp": tp, "fp": fp, "fn": fn}
