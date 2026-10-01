"""AI-2 fusion evaluation over SYNTHETIC held-out duplicate pairs."""
from __future__ import annotations

import copy
from datetime import datetime
from typing import Sequence

from ai.evaluation import metrics as M
from ai.inference.config import load_fusion_policy
from ai.inference.fusion.scoring import FusionWeights
from ai.inference.fusion.service import FusionService
from ai.inference.provider import AIProvider
from ai.inference.schemas import FusionCase, FusionRequest


def _case(d: dict) -> FusionCase:
    return FusionCase(case_id=d["case_id"], category=d["category"], subcategory=d["subcategory"],
                      latitude=d["latitude"], longitude=d["longitude"],
                      created_at=datetime.fromisoformat(d["created_at"]), text=d["text"])


def evaluate(pairs: Sequence[dict], weights: FusionWeights | None = None, provider: AIProvider | None = None,
             embedding_weights: FusionWeights | None = None) -> dict:
    policy = copy.deepcopy(load_fusion_policy())
    policy["thresholds"]["related"] = 0.0     # return every gated candidate so raw scores can be evaluated
    svc = FusionService(provider=provider, weights=weights, policy=policy, embedding_weights=embedding_weights)
    th = load_fusion_policy()["thresholds"]
    scores, labels, kinds, cross = [], [], [], []
    gated_out = {"positive": 0, "negative": 0}
    for p in pairs:
        a, b = _case(p["a"]), _case(p["b"])
        resp = svc.analyze(FusionRequest(subject=a, candidates=[b]))
        if not resp.matches:       # outside candidate gate (radius / window / category)
            gated_out["positive" if p["label"] else "negative"] += 1
            continue
        scores.append(resp.matches[0].similarity)
        labels.append(p["label"])
        kinds.append(p["pair_type"])
        cross.append(p["cross_language"])
    n_pos = sum(p["label"] for p in pairs)
    out = {
        "task": "fusion", "n_pairs": len(pairs), "n_gated_in": len(scores),
        "gate_recall_of_true_duplicates": round(1 - gated_out["positive"] / n_pos, 4) if n_pos else None,
        "negatives_removed_by_gate": gated_out["negative"],
        "auc_roc": round(M.auc_roc(scores, labels), 4),
        "at_possible_duplicate_threshold": {k: (round(v, 4) if isinstance(v, float) else v)
                                            for k, v in M.precision_recall_at(scores, labels, th["possible_duplicate"]).items()},
        "weights_status": (svc.embedding_weights if provider else svc.weights).status,
        "semantic_trained_on": (svc.embedding_weights if provider else svc.weights).semantic_trained_on,
        "semantic_source": "embedding" if provider else "lexical",
    }
    for name, sel in (("same_language", [i for i, c in enumerate(cross) if not c]),
                      ("cross_language", [i for i, c in enumerate(cross) if c])):
        if sel:
            m = M.precision_recall_at([scores[i] for i in sel], [labels[i] for i in sel], th["possible_duplicate"])
            out[name] = {"n": len(sel), "recall": round(m["recall"], 4), "precision": round(m["precision"], 4)}
    by_kind = {}
    for k in sorted(set(kinds)):
        ks = [s for s, kk in zip(scores, kinds) if kk == k]
        by_kind[k] = {"n": len(ks), "mean_score": round(sum(ks) / len(ks), 4),
                      "flagged_possible_duplicate": round(sum(s >= th["possible_duplicate"] for s in ks) / len(ks), 4)}
    out["by_pair_type"] = by_kind
    out["caveat"] = ("SYNTHETIC pairs: duplicates are constructed with small GPS jitter, so geospatial distance "
                     "dominates. High scores here do not predict real-world performance.")
    return out
