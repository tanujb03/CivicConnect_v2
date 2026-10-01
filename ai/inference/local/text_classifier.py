"""Local multilingual text classifier (B0: char-n-gram TF-IDF + logistic regression).

Loads a versioned artifact directory and scores text with numpy only (no
scikit-learn, no pickle). Used as (a) the offline/unavailable-provider fallback
for AI-1 intake, (b) a cheap cross-check on the provider's answer, (c) the
baseline in the shared evaluation harness.

Artifact layout (``ai/artifacts/<model_name>/<version>/``)::

    manifest.json   schema, label IDs, vectoriser config, calibration, file hashes
    weights.npz     coef [labels x features], intercept [labels], idf [features]
    vocab.json      n-gram -> feature index
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..config import Taxonomy, load_taxonomy
from ..errors import ArtifactError
from .featurizer import NORMALIZER_VERSION, CharNgramVectorizer

ARTIFACT_SCHEMA = "civic-text-classifier/1"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max()
    e = np.exp(z)
    return e / e.sum()


@dataclass
class LocalPrediction:
    label_id: str                       # "category/subcategory"
    category: str
    subcategory: str
    category_probability: float         # marginal over the category's subcategories
    subcategory_probability: float
    top_k: list[tuple[str, float]]      # (label_id, calibrated probability)
    explanation_terms: list[str] = field(default_factory=list)
    abstained: bool = False             # no known n-gram in the input
    model_name: str = ""
    model_version: str = ""


class LocalTextClassifier:
    def __init__(self, manifest: dict, vectorizer: CharNgramVectorizer, coef: np.ndarray,
                 intercept: np.ndarray, taxonomy: Taxonomy):
        self.manifest = manifest
        self.vectorizer = vectorizer
        self.coef = coef
        self.intercept = intercept
        self.taxonomy = taxonomy
        self.label_ids: list[str] = manifest["label_ids"]
        self.temperature = float(manifest.get("calibration", {}).get("temperature", 1.0))
        self._inv_vocab: list[str] | None = None
        self._cat_index: dict[str, list[int]] = {}
        for i, lid in enumerate(self.label_ids):
            self._cat_index.setdefault(lid.split("/", 1)[0], []).append(i)

    # ---- loading ---------------------------------------------------------- #
    @classmethod
    def load(cls, path: str | Path, taxonomy: Taxonomy | None = None) -> "LocalTextClassifier":
        taxonomy = taxonomy or load_taxonomy()
        d = Path(path)
        mf = d / "manifest.json"
        if not mf.is_file():
            raise ArtifactError(f"manifest.json not found in {d}")
        try:
            manifest = json.loads(mf.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ArtifactError(f"manifest.json is not valid JSON: {e}") from e
        if manifest.get("artifact_schema") != ARTIFACT_SCHEMA:
            raise ArtifactError(
                f"unsupported artifact_schema {manifest.get('artifact_schema')!r}; expected {ARTIFACT_SCHEMA!r}"
            )
        vcfg = manifest.get("vectorizer", {})
        if vcfg.get("normalizer") != NORMALIZER_VERSION:
            raise ArtifactError(f"normaliser mismatch: artifact {vcfg.get('normalizer')!r} vs code {NORMALIZER_VERSION!r}")
        for name, expected in manifest.get("files", {}).items():
            f = d / name
            if not f.is_file():
                raise ArtifactError(f"artifact file missing: {name}")
            if sha256_file(f) != expected:
                raise ArtifactError(f"checksum mismatch for {name} (artifact corrupt or modified)")
        try:
            vocab = json.loads((d / "vocab.json").read_text(encoding="utf-8"))
            with np.load(d / "weights.npz", allow_pickle=False) as w:
                coef, intercept, idf = w["coef"], w["intercept"], w["idf"]
        except (OSError, KeyError, ValueError) as e:
            raise ArtifactError(f"cannot read artifact arrays: {e}") from e
        labels = manifest["label_ids"]
        if coef.shape != (len(labels), len(vocab)) or intercept.shape != (len(labels),) or idf.shape != (len(vocab),):
            raise ArtifactError(f"array shapes inconsistent with manifest: coef {coef.shape}, labels {len(labels)}, vocab {len(vocab)}")
        for lid in labels:
            cat, _, sub = lid.partition("/")
            if not taxonomy.is_valid_pair(cat, sub):
                raise ArtifactError(f"label {lid!r} is not in taxonomy {taxonomy.version}")
        vec = CharNgramVectorizer(vocab, idf, tuple(vcfg["ngram_range"]), vcfg.get("sublinear_tf", True))
        return cls(manifest, vec, coef.astype(np.float32), intercept.astype(np.float32), taxonomy)

    # ---- inference -------------------------------------------------------- #
    @property
    def model_name(self) -> str:
        return self.manifest.get("model_name", "local")

    @property
    def model_version(self) -> str:
        return str(self.manifest.get("model_version", ""))

    def predict_proba(self, text: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        idx, val = self.vectorizer.transform_one(text)
        logits = self.intercept.astype(np.float64).copy()
        if idx.size:
            logits += self.coef[:, idx].astype(np.float64) @ val.astype(np.float64)
        return _softmax(logits / self.temperature), idx, val

    def predict(self, text: str, top_k: int = 3, explain_k: int = 5) -> LocalPrediction:
        probs, idx, val = self.predict_proba(text)
        abstained = idx.size == 0
        order = np.argsort(-probs, kind="stable")
        best = int(order[0])
        lid = self.label_ids[best]
        cat, _, sub = lid.partition("/")
        cat_prob = float(sum(probs[i] for i in self._cat_index[cat]))
        terms: list[str] = []
        if not abstained and explain_k:
            contrib = self.coef[best, idx].astype(np.float64) * val.astype(np.float64)
            inv = self._inverse_vocab()
            for j in np.argsort(-contrib, kind="stable")[: explain_k * 3]:
                if contrib[j] <= 0:
                    break
                term = inv[int(idx[j])].strip()
                if len(term) >= 3 and not any(term in t or t in term for t in terms):
                    terms.append(term)
                if len(terms) >= explain_k:
                    break
        return LocalPrediction(
            label_id=lid, category=cat, subcategory=sub,
            category_probability=cat_prob, subcategory_probability=float(probs[best]),
            top_k=[(self.label_ids[int(i)], float(probs[int(i)])) for i in order[:top_k]],
            explanation_terms=terms, abstained=abstained,
            model_name=self.model_name, model_version=self.model_version,
        )

    def _inverse_vocab(self) -> list[str]:
        if self._inv_vocab is None:
            inv = [""] * len(self.vectorizer.vocab)
            for g, i in self.vectorizer.vocab.items():
                inv[i] = g
            self._inv_vocab = inv
        return self._inv_vocab
