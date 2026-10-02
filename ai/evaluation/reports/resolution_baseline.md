# Evaluation report — resolution_baseline

> **SYNTHETIC DATA ONLY — not an estimate of real-world accuracy.**

> Read the provenance and claims blocks first. Synthetic results are a regression/ablation signal, NOT real-world accuracy; real-data results are scoped to the named dataset, holdout and (draft) taxonomy mapping.

- Track: `synthetic`  |  Task: `resolution`  |  System: `rules`  |  Created: 2026-10-02T18:36:07+00:00
- Artifact: `None`
- Real-world accuracy claim allowed: **False** (all rows are synthetic)

## Dataset provenance

| source | kind | n | licence (verified?) | origin verified? | label origin | text origin | mapping |
|---|---|---|---|---|---|---|---|
| synthetic_civic | synthetic | 240 | project-owned (yes) | yes | {'synthetic_template': 240} | {'n/a': 240} | None  |

Files: {"resolution_v1": "resolution-scenarios/1"}

## Results

```json
{
  "task": "resolution",
  "n": 240,
  "n_truly_unresolved": 77,
  "mode": "deterministic baseline (no provider)",
  "unresolved_flag_recall": 0.6364,
  "unresolved_flag_false_positive_rate": 0.0,
  "verification_request_recall_of_unresolved": 1.0,
  "verification_request_rate_when_truly_fixed": 0.5215,
  "verification_request_rate_when_truly_fixed_and_citizen_confirmed": 0.0,
  "insufficient_evidence_correct_when_no_resolution_photo": 1.0,
  "autonomous_closure_allowed_any": false,
  "monotonic_violations_with_optimistic_ai": 0,
  "unresolved_by_detectable_signal": {
    "citizen_signal": {
      "n": 49,
      "flagged_unresolved": 1.0,
      "verification_requested": 1.0
    },
    "notes_text": {
      "n": 16,
      "flagged_unresolved": 0.0,
      "verification_requested": 1.0
    },
    "images_only": {
      "n": 12,
      "flagged_unresolved": 0.0,
      "verification_requested": 1.0
    }
  },
  "outside_deterministic_baseline": {
    "share_of_unresolved_only_in_field_notes": 0.2078,
    "share_of_unresolved_only_visible_in_photos": 0.1558,
    "meaning": "The baseline never reads note text or pixels. These cases are caught only by the citizen-verification step (every unconfirmed case gets a request) or by the multimodal provider path, which is NOT evaluated here (no before/after images exist)."
  },
  "archetypes": {
    "fixed_confirmed": 69,
    "fixed_pending": 61,
    "fixed_sparse": 16,
    "no_after_evidence": 17,
    "partial_reported": 16,
    "unfixed_reported": 33,
    "unfixed_silent_no_signal": 12,
    "unfixed_silent_notes": 16
  },
  "not_evaluated": [
    "multimodal provider comparison (needs real before/after images + a configured model)",
    "field-note understanding by a language model"
  ]
}
```

## Limitations
- Hindi/Marathi synthetic text is unreviewed by native speakers; real city data are not Indian-language narratives.
- Single held-out split: wide confidence intervals; use k-fold where available.
