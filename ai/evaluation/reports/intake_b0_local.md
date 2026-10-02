# Evaluation report — intake_b0_local

> **SYNTHETIC DATA ONLY — not an estimate of real-world accuracy.**

> Read the provenance and claims blocks first. Synthetic results are a regression/ablation signal, NOT real-world accuracy; real-data results are scoped to the named dataset, holdout and (draft) taxonomy mapping.

- Track: `synthetic`  |  Task: `intake`  |  System: `local`  |  Created: 2026-10-02T18:36:05+00:00
- Artifact: `civic_text_b0@0.1.0+b22811b6`
- Real-world accuracy claim allowed: **False** (all rows are synthetic)

## Dataset provenance

| source | kind | n | licence (verified?) | origin verified? | label origin | text origin | mapping |
|---|---|---|---|---|---|---|---|
| synthetic_civic | synthetic | 216 | project-owned (yes) | yes | {'synthetic_template': 216} | {'n/a': 216} | None  |

Files: {"intake_eval.v1.jsonl": "3c749d0d432293e3"}

## Results

| metric | value |
|---|---|
| category_accuracy | 0.6157 |
| subcategory_accuracy | 0.5463 |
| subcategory_macro_f1 | 0.5223 |
| routing_accuracy_department | 0.6157 |
| calibration_ece_category | 0.0632 |
| coverage_at_threshold | 0.6296 |
| category_accuracy_when_accepted | 0.7279 |
| structured_output_validity | 1.0 |
| degraded_rate | 1.0 |
| severity_agreement | 0.662 |

95% CI for subcategory accuracy: [0.48, 0.611]

_CIRCULAR on synthetic data: gold severity is derived from the same taxonomy+keyword assumptions as the rules. Measures rule consistency only._

**By language**

| language | n | subcategory acc | category acc |
|---|---|---|---|
| en | 54 | 0.5185 | 0.537 |
| hi | 54 | 0.5741 | 0.6667 |
| hi-Latn | 54 | 0.4815 | 0.6296 |
| mr | 54 | 0.6111 | 0.6296 |

**Code-mixed / noisy**

| slice | n | subcategory acc |
|---|---|---|
| code_mixed=False | 171 | 0.5497 |
| code_mixed=True | 45 | 0.5333 |
| noisy=False | 112 | 0.5536 |
| noisy=True | 104 | 0.5385 |

**Top confusions**

- roads/pothole → parks_trees/fallen_tree ×7
- water_supply/contaminated_water → drainage_sewerage/sewage_overflow ×7
- public_health/mosquito_breeding → roads/pothole ×6
- traffic_encroachment/footpath_encroachment → sanitation/illegal_dumping ×5
- traffic_encroachment/signal_not_working → street_lighting/light_not_working ×4
- public_health/stray_animals → traffic_encroachment/illegal_parking ×4
- parks_trees/damaged_park_equipment → roads/road_cave_in ×4
- public_health/stray_animals → roads/pothole ×4

## Limitations
- Hindi/Marathi synthetic text is unreviewed by native speakers; real city data are not Indian-language narratives.
- Single held-out split: wide confidence intervals; use k-fold where available.
