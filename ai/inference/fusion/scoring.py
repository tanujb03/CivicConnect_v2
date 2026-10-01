"""Calibrated combined scoring: a logistic model over the four signals.

Weights come from ``train_fusion_calibrator`` (fitted on *synthetic* labelled
pairs) or fall back to the documented, uncalibrated prior in
``fusion_policy.v1.json``. The status is carried into responses so an
uncalibrated score is never presented as calibrated.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from ..errors import ArtifactError

WEIGHTS_SCHEMA = "civic-fusion-weights/1"
FEATURES = ("semantic", "geospatial", "temporal", "category")


@dataclass(frozen=True)
class FusionWeights:
    bias: float
    semantic: float
    geospatial: float
    temporal: float
    category: float
    status: str = "uncalibrated_prior"          # or "calibrated_synthetic"
    semantic_trained_on: str = "none"           # "lexical" | "embedding" | "none"
    version: str = "prior"

    @classmethod
    def from_prior(cls, policy: dict) -> "FusionWeights":
        p = policy["prior_weights"]
        return cls(p["bias"], p["semantic"], p["geospatial"], p["temporal"], p["category"],
                   status=p.get("status", "uncalibrated_prior"))

    @classmethod
    def load(cls, path: str | Path) -> "FusionWeights":
        p = Path(path)
        f = p / "fusion_weights.json" if p.is_dir() else p
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise ArtifactError(f"cannot read fusion weights {f}: {e}") from e
        if d.get("schema") != WEIGHTS_SCHEMA:
            raise ArtifactError(f"unsupported fusion weights schema {d.get('schema')!r}")
        try:
            return cls(float(d["bias"]), float(d["semantic"]), float(d["geospatial"]),
                       float(d["temporal"]), float(d["category"]), status=d.get("status", "calibrated_synthetic"),
                       semantic_trained_on=d.get("semantic_trained_on", "lexical"), version=str(d.get("version", "")))
        except (KeyError, TypeError, ValueError) as e:
            raise ArtifactError(f"fusion weights malformed: {e}") from e

    def score(self, semantic: float, geospatial: float, temporal: float, category: float) -> float:
        z = (self.bias + self.semantic * semantic + self.geospatial * geospatial
             + self.temporal * temporal + self.category * category)
        return 1.0 / (1.0 + math.exp(-z))
