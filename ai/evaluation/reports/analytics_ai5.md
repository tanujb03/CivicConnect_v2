# Evaluation report — analytics_ai5

> **SYNTHETIC DATA ONLY — not an estimate of real-world accuracy.**

> Read the provenance and claims blocks first. Synthetic results are a regression/ablation signal, NOT real-world accuracy; real-data results are scoped to the named dataset, holdout and (draft) taxonomy mapping.

- Track: `synthetic`  |  Task: `analytics_ai5`  |  System: `rules+scripted`  |  Created: 2026-10-02T18:37:39+00:00
- Artifact: `None`
- Real-world accuracy claim allowed: **False** (all rows are synthetic)

## Dataset provenance

| source | kind | n | licence (verified?) | origin verified? | label origin | text origin | mapping |
|---|---|---|---|---|---|---|---|
| synthetic_civic | synthetic | 560 | project-owned (yes) | yes | {'synthetic_template': 560} | {'n/a': 560} | None  |

Files: {"demo_city_v1": "demo_city_v1"}

## Results

```json
{
  "task": "analytics_ai5",
  "facts": {
    "hotspot_recall": 1.0,
    "growth_recall_of_planted_hotspot_subcategories": 1.0,
    "growth_explained_by_planted_incidents": [
      "exposed_live_wire"
    ],
    "growth_unexplained_subcategories": [],
    "recurring_sites_recall_in_facts": 0.3333,
    "recurring_note": "Facts list only the top 5 recurring sites, so recall below 1.0 is a display cap, not a detection failure (see demo-city recovery).",
    "active_incident_recall": 1.0,
    "reproducible": true,
    "fact_ids_unique": true,
    "n_facts_city": 26,
    "department_scope_total_matches": true
  },
  "explanation_guard_rails": {
    "scopes_tested": 7,
    "honest_provider_prose_accepted": 1.0,
    "hallucinated_numbers_rejected_and_replaced": 1.0,
    "unknown_fact_ids_rejected_and_replaced": 1.0,
    "ungrounded_numbers_in_any_final_output": 0,
    "template_summary_mentions_planted_hotspot_when_present": true,
    "all_outputs_grounded_flag": true
  },
  "not_evaluated": [
    "quality/usefulness of a real LLM's wording",
    "multilingual explanations",
    "staff comprehension"
  ],
  "provider_note": "Providers in this report are scripted test doubles, not model outputs."
}
```

## Limitations
- Hindi/Marathi synthetic text is unreviewed by native speakers; real city data are not Indian-language narratives.
- Single held-out split: wide confidence intervals; use k-fold where available.
