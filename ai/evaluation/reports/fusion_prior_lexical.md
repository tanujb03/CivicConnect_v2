# Evaluation report — fusion_prior_lexical

> **SYNTHETIC DATA ONLY — not an estimate of real-world accuracy.**

> Read the provenance and claims blocks first. Synthetic results are a regression/ablation signal, NOT real-world accuracy; real-data results are scoped to the named dataset, holdout and (draft) taxonomy mapping.

- Track: `synthetic`  |  Task: `fusion`  |  System: `lexical`  |  Created: 2026-10-02T18:36:07+00:00
- Artifact: `uncalibrated_prior`
- Real-world accuracy claim allowed: **False** (all rows are synthetic)

## Dataset provenance

| source | kind | n | licence (verified?) | origin verified? | label origin | text origin | mapping |
|---|---|---|---|---|---|---|---|
| synthetic_civic | synthetic | 300 | project-owned (yes) | yes | {'synthetic_template': 300} | {'n/a': 300} | None  |

Files: {"fusion_eval_pairs.v1.jsonl": "503f4ddc08aa5e23"}

## Results

```json
{
  "task": "fusion",
  "n_pairs": 300,
  "n_gated_in": 255,
  "gate_recall_of_true_duplicates": 1.0,
  "negatives_removed_by_gate": 45,
  "auc_roc": 0.9297,
  "at_possible_duplicate_threshold": {
    "threshold": 0.8,
    "precision": 0.9359,
    "recall": 0.6083,
    "f1": 0.7374,
    "tp": 73,
    "fp": 5,
    "fn": 47
  },
  "weights_status": "uncalibrated_prior",
  "semantic_trained_on": "none",
  "semantic_source": "lexical",
  "same_language": {
    "n": 177,
    "recall": 0.7831,
    "precision": 0.9286
  },
  "cross_language": {
    "n": 78,
    "recall": 0.2162,
    "precision": 1.0
  },
  "caveat": "SYNTHETIC pairs: duplicates are constructed with small GPS jitter, so geospatial distance dominates. High scores here do not predict real-world performance."
}
```

| pair type | n | mean score | flagged duplicate |
|---|---|---|---|
| distinct_near | 75 | 0.5316 | 0.0667 |
| duplicate | 120 | 0.8091 | 0.6083 |
| related_category | 60 | 0.4069 | 0.0 |

## Limitations
- Hindi/Marathi synthetic text is unreviewed by native speakers; real city data are not Indian-language narratives.
- Single held-out split: wide confidence intervals; use k-fold where available.
