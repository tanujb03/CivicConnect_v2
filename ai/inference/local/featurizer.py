"""Text normalisation and char-n-gram TF-IDF featurisation.

This module is the **single source of truth** for featurisation: training imports
it to build the vocabulary/IDF and the design matrix, and inference imports it to
score text. That removes train/serve skew by construction (the only thing
training adds is *fitting* the vocabulary and the linear weights).
"""
from __future__ import annotations

import math
import unicodedata
from collections import Counter
from typing import Iterator, Sequence

import numpy as np

NORMALIZER_VERSION = "civic-norm/1"
ANALYZER = "char_wb"

_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"), None)


def normalize_text(text: str) -> str:
    """NFKC, casefold, drop zero-width chars, keep letters/marks/digits only."""
    t = unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH).casefold()
    kept = [ch if unicodedata.category(ch)[0] in "LMN" else " " for ch in t]
    return " ".join("".join(kept).split())


def char_wb_ngrams(normalized: str, ngram_range: tuple[int, int] = (2, 4)) -> Iterator[str]:
    """Word-boundary-padded character n-grams (scikit-learn ``char_wb`` style)."""
    lo, hi = ngram_range
    for word in normalized.split():
        padded = f" {word} "
        for n in range(lo, hi + 1):
            for i in range(len(padded) - n + 1):
                yield padded[i : i + n]


def count_ngrams(text: str, ngram_range: tuple[int, int] = (2, 4)) -> Counter:
    return Counter(char_wb_ngrams(normalize_text(text), ngram_range))


class CharNgramVectorizer:
    """Fitted TF-IDF vectoriser: vocabulary + IDF are plain data."""

    def __init__(
        self,
        vocab: dict[str, int],
        idf: np.ndarray,
        ngram_range: tuple[int, int] = (2, 4),
        sublinear_tf: bool = True,
    ):
        if len(vocab) != len(idf):
            raise ValueError("vocab and idf length mismatch")
        self.vocab = vocab
        self.idf = np.asarray(idf, dtype=np.float32)
        self.ngram_range = (int(ngram_range[0]), int(ngram_range[1]))
        self.sublinear_tf = sublinear_tf

    @property
    def n_features(self) -> int:
        return len(self.vocab)

    def transform_one(self, text: str) -> tuple[np.ndarray, np.ndarray]:
        """Return (sorted feature indices, L2-normalised TF-IDF values)."""
        counts = count_ngrams(text, self.ngram_range)
        pairs = sorted((self.vocab[g], c) for g, c in counts.items() if g in self.vocab)
        if not pairs:
            return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float32)
        idx = np.fromiter((p[0] for p in pairs), dtype=np.int64, count=len(pairs))
        tf = np.fromiter(
            ((1.0 + math.log(p[1])) if self.sublinear_tf else float(p[1]) for p in pairs),
            dtype=np.float64,
            count=len(pairs),
        )
        val = tf * self.idf[idx].astype(np.float64)
        norm = float(np.sqrt((val * val).sum()))
        if norm > 0:
            val = val / norm
        return idx, val.astype(np.float32)

    def transform_many(self, texts: Sequence[str]) -> list[tuple[np.ndarray, np.ndarray]]:
        return [self.transform_one(t) for t in texts]
