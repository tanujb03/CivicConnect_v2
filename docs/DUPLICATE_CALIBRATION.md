# Duplicate threshold calibration

> **SYNTHETIC demo data: no real-world claim. The thresholds below are a starting point to be re-checked on real reports.**

> CAUTION: only 27 positive pairs (fewer than 30): the precision and the chosen thresholds are very uncertain. SYNTHETIC demo data: no real-world claim. The thresholds below are a starting point to be re-checked on real reports.
> fused: duplicate_threshold: 0.94 reaches precision >= 0.90 with only 1 true positives (< 5): too little support

## Inputs

- Gate (`fusion_policy.v1.json` candidate_generation, deterministic and primary): same category = True, radius 150 m, time window 30 days.
- Embeddings read from `case_embeddings`: model `provider:gemini-embedding-001`, 768 dimensions (models seen: provider:gemini-embedding-001). 504 of 560 demo cases have one (56 lack one); 504 of the 504 cases in the pairs below (100%); 100% of the cases of the planted duplicate pairs have a comparable vector.
- Random sample of out-of-gate pairs: fixed seed 7.

## Pairs

- Positives: 27 planted duplicate pairs (`possible_duplicate_pairs`), 27 pass the gate, 0 do not (a gate miss no threshold can fix).
- Not evaluable at case level: 49 report pairs inside merged cases (`duplicate_groups_merged`: one case, one embedding).
- Hard negatives: 18 of 18 `near_distinct_pairs` pass the gate; 498 other pairs pass the gate (may hide unlabelled duplicates).
- Out-of-gate random pairs: 500. Scored (both vectors comparable): positives 27, near_distinct 18, other_gated 498, out_of_gate 500; dropped for a missing or incomparable vector: positives 0, near_distinct 0, other_gated 0, out_of_gate 0.

## Cosine similarity by class

| class | n | min | p10 | median | p90 | max |
|---|---:|---:|---:|---:|---:|---:|
| planted duplicates (in gate) | 27 | 0.584 | 0.712 | 0.814 | 0.882 | 0.943 |
| near-distinct pairs (in gate) | 18 | 0.667 | 0.689 | 0.768 | 0.838 | 0.914 |
| other pairs in the gate | 498 | 0.536 | 0.665 | 0.768 | 0.854 | 0.971 |
| random pairs OUT of the gate (baseline) | 500 | 0.505 | 0.559 | 0.647 | 0.732 | 0.938 |

The out-of-gate row is the baseline: unrelated cases are NOT low, so a bare cosine cutoff cannot replace the gate.

## Cosine threshold sweep (inside the gate)

| threshold | TP | FP | FN | precision | recall | F1 | precision vs near-distinct only |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.50 | 27 | 516 | 0 | 0.050 | 1.000 | 0.095 | 0.600 |
| 0.52 | 27 | 516 | 0 | 0.050 | 1.000 | 0.095 | 0.600 |
| 0.54 | 27 | 515 | 0 | 0.050 | 1.000 | 0.095 | 0.600 |
| 0.56 | 27 | 515 | 0 | 0.050 | 1.000 | 0.095 | 0.600 |
| 0.58 | 27 | 511 | 0 | 0.050 | 1.000 | 0.096 | 0.600 |
| 0.60 | 26 | 507 | 1 | 0.049 | 0.963 | 0.093 | 0.591 |
| 0.62 | 26 | 502 | 1 | 0.049 | 0.963 | 0.094 | 0.591 |
| 0.64 | 26 | 487 | 1 | 0.051 | 0.963 | 0.096 | 0.591 |
| 0.66 | 26 | 471 | 1 | 0.052 | 0.963 | 0.099 | 0.591 |
| 0.68 | 26 | 447 | 1 | 0.055 | 0.963 | 0.104 | 0.619 |
| 0.70 | 25 | 419 | 2 | 0.056 | 0.926 | 0.106 | 0.625 |
| 0.72 | 23 | 387 | 4 | 0.056 | 0.852 | 0.105 | 0.639 |
| 0.74 | 22 | 344 | 5 | 0.060 | 0.815 | 0.112 | 0.647 |
| 0.76 | 21 | 282 | 6 | 0.069 | 0.778 | 0.127 | 0.677 |
| 0.78 | 19 | 220 | 8 | 0.079 | 0.704 | 0.143 | 0.731 |
| 0.80 | 17 | 159 | 10 | 0.097 | 0.630 | 0.167 | 0.810 |
| 0.82 | 12 | 112 | 15 | 0.097 | 0.444 | 0.159 | 0.857 |
| 0.84 | 7 | 79 | 20 | 0.081 | 0.259 | 0.124 | 0.778 |
| 0.86 | 4 | 48 | 23 | 0.077 | 0.148 | 0.101 | 0.667 |
| 0.88 | 3 | 31 | 24 | 0.088 | 0.111 | 0.098 | 0.600 |
| 0.90 | 3 | 20 | 24 | 0.130 | 0.111 | 0.120 | 0.750 |
| 0.92 | 1 | 11 | 26 | 0.083 | 0.037 | 0.051 | 1.000 |
| 0.94 | 1 | 6 | 26 | 0.143 | 0.037 | 0.059 | 1.000 |
| 0.96 | 0 | 2 | 27 | 0.000 | 0.000 | 0.000 | - |
| 0.98 | 0 | 0 | 27 | - | 0.000 | 0.000 | - |

## Chosen cosine thresholds

- `duplicate_threshold` = **0.80** (F1-maximising threshold (no threshold reaches precision >= 0.90 with at least 5 true positives)): precision 0.097, recall 0.630, F1 0.167 (TP 17, FP 159, FN 10)
- `related_threshold` = **0.80** (F1-maximising threshold (no threshold reaches precision >= 0.75)): precision 0.097, recall 0.630, F1 0.167 (TP 17, FP 159, FN 10)
- WARNING: duplicate_threshold: no threshold on the grid reaches precision >= 0.90 with at least 5 true positives; the F1-maximising threshold 0.80 is shown instead
- WARNING: related_threshold: no threshold on the grid reaches precision >= 0.75; the F1-maximising threshold 0.80 is shown instead

## Against the policy file (fused score)

The thresholds in `fusion_policy.v1.json` (possible_duplicate 0.8, related 0.5) apply to the FUSED score (cosine + distance + time + category, weights status `uncalibrated_prior`), not to the raw cosine above. The same rule applied to the fused score:

| class | n | min | p10 | median | p90 | max |
|---|---:|---:|---:|---:|---:|---:|
| planted duplicates (in gate) | 27 | 0.829 | 0.875 | 0.913 | 0.926 | 0.941 |
| near-distinct pairs (in gate) | 18 | 0.446 | 0.500 | 0.601 | 0.742 | 0.824 |
| other pairs in the gate | 498 | 0.228 | 0.457 | 0.730 | 0.873 | 0.934 |
| random pairs OUT of the gate (baseline) | 500 | 0.077 | 0.086 | 0.106 | 0.237 | 0.848 |

- `duplicate_threshold` = **0.90** (F1-maximising threshold (no threshold reaches precision >= 0.90 with at least 5 true positives)): precision 0.450, recall 0.667, F1 0.537 (TP 18, FP 22, FN 9)
- `related_threshold` = **0.90** (capped at the duplicate threshold (the fallback gave a higher value)): precision 0.450, recall 0.667, F1 0.537 (TP 18, FP 22, FN 9)

- duplicate: policy 0.80 (precision 0.143, recall 1.000 at the grid point 0.80) vs chosen 0.90 (difference +0.10): WOULD CHANGE
- related: policy 0.50 (precision 0.057, recall 1.000 at the grid point 0.50) vs chosen 0.90 (difference +0.40): WOULD CHANGE

The policy file was not edited; applying a change is a decision for a human.

<details><summary>Fused-score sweep</summary>

| threshold | TP | FP | FN | precision | recall | F1 | precision vs near-distinct only |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.50 | 27 | 448 | 0 | 0.057 | 1.000 | 0.108 | 0.628 |
| 0.52 | 27 | 438 | 0 | 0.058 | 1.000 | 0.110 | 0.659 |
| 0.54 | 27 | 425 | 0 | 0.060 | 1.000 | 0.113 | 0.711 |
| 0.56 | 27 | 417 | 0 | 0.061 | 1.000 | 0.115 | 0.711 |
| 0.58 | 27 | 400 | 0 | 0.063 | 1.000 | 0.119 | 0.730 |
| 0.60 | 27 | 387 | 0 | 0.065 | 1.000 | 0.122 | 0.750 |
| 0.62 | 27 | 372 | 0 | 0.068 | 1.000 | 0.127 | 0.771 |
| 0.64 | 27 | 358 | 0 | 0.070 | 1.000 | 0.131 | 0.794 |
| 0.66 | 27 | 332 | 0 | 0.075 | 1.000 | 0.140 | 0.794 |
| 0.68 | 27 | 313 | 0 | 0.079 | 1.000 | 0.147 | 0.794 |
| 0.70 | 27 | 286 | 0 | 0.086 | 1.000 | 0.159 | 0.818 |
| 0.72 | 27 | 268 | 0 | 0.092 | 1.000 | 0.168 | 0.871 |
| 0.74 | 27 | 236 | 0 | 0.103 | 1.000 | 0.186 | 0.931 |
| 0.76 | 27 | 209 | 0 | 0.114 | 1.000 | 0.205 | 0.964 |
| 0.78 | 27 | 183 | 0 | 0.129 | 1.000 | 0.228 | 0.964 |
| 0.80 | 27 | 162 | 0 | 0.143 | 1.000 | 0.250 | 0.964 |
| 0.82 | 27 | 134 | 0 | 0.168 | 1.000 | 0.287 | 0.964 |
| 0.84 | 26 | 97 | 1 | 0.211 | 0.963 | 0.347 | 1.000 |
| 0.86 | 25 | 71 | 2 | 0.260 | 0.926 | 0.407 | 1.000 |
| 0.88 | 21 | 40 | 6 | 0.344 | 0.778 | 0.477 | 1.000 |
| 0.90 | 18 | 22 | 9 | 0.450 | 0.667 | 0.537 | 1.000 |
| 0.92 | 6 | 4 | 21 | 0.600 | 0.222 | 0.324 | 1.000 |
| 0.94 | 1 | 0 | 26 | 1.000 | 0.037 | 0.071 | 1.000 |
| 0.96 | 0 | 0 | 27 | - | 0.000 | 0.000 | - |
| 0.98 | 0 | 0 | 27 | - | 0.000 | 0.000 | - |

</details>
