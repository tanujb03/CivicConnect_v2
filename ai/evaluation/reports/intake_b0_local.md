# Evaluation report — intake_b0_local

> **SYNTHETIC DATA ONLY — not an estimate of real-world accuracy.**

> Read the provenance and claims blocks first. Synthetic results are a regression/ablation signal, NOT real-world accuracy; real-data results are scoped to the named dataset, holdout and (draft) taxonomy mapping.

- Track: `synthetic`  |  Task: `intake`  |  System: `local`  |  Created: 2026-10-01T12:16:20+00:00
- Artifact: `civic_text_b0@0.1.0+addecff1`
- Real-world accuracy claim allowed: **False** (all rows are synthetic)

## Dataset provenance

| source | kind | n | licence (verified?) | label origin | text origin | mapping |
|---|---|---|---|---|---|---|
| synthetic_civic | synthetic | 216 | project-owned (yes) | {'synthetic_template': 216} | {'n/a': 216} | None  |

Files: {"intake_eval.v1.jsonl": "3c749d0d432293e3"}

## Results

| metric | value |
|---|---|
| category_accuracy | 0.6157 |
| subcategory_accuracy | 0.5556 |
| subcategory_macro_f1 | 0.5295 |
| routing_accuracy_department | 0.6157 |
| calibration_ece_category | 0.0678 |
| coverage_at_threshold | 0.5926 |
| category_accuracy_when_accepted | 0.7344 |
| structured_output_validity | 1.0 |
| degraded_rate | 1.0 |
| severity_agreement | 0.6759 |

95% CI for subcategory accuracy: [0.489, 0.62]

_CIRCULAR on synthetic data: gold severity is derived from the same taxonomy+keyword assumptions as the rules. Measures rule consistency only._

**By language**

| language | n | subcategory acc | category acc |
|---|---|---|---|
| en | 54 | 0.5185 | 0.5185 |
| hi | 54 | 0.5741 | 0.6667 |
| hi-Latn | 54 | 0.4815 | 0.6111 |
| mr | 54 | 0.6481 | 0.6667 |

**Code-mixed / noisy**

| slice | n | subcategory acc |
|---|---|---|
| code_mixed=False | 171 | 0.5556 |
| code_mixed=True | 45 | 0.5556 |
| noisy=False | 112 | 0.5536 |
| noisy=True | 104 | 0.5577 |

**Top confusions**

- roads/pothole → parks_trees/fallen_tree ×7
- public_health/mosquito_breeding → roads/pothole ×7
- water_supply/contaminated_water → drainage_sewerage/sewage_overflow ×7
- public_health/stray_animals → roads/pothole ×5
- parks_trees/damaged_park_equipment → roads/road_cave_in ×4
- traffic_encroachment/footpath_encroachment → sanitation/illegal_dumping ×4
- sanitation/illegal_dumping → roads/damaged_footpath ×4
- roads/road_cave_in → parks_trees/damaged_park_equipment ×4

## Limitations
- Hindi/Marathi synthetic text is unreviewed by native speakers; real city data are not Indian-language narratives.
- Single held-out split: wide confidence intervals; use k-fold where available.
