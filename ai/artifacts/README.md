# ai/artifacts

Canonical location for generated model/data artifacts (system design Section 49; common directory structure).

| Path | Tracked? | Contents |
|---|---|---|
| `fixtures/b0_tiny/` | yes (~150 KB) | Tiny deterministic classifier used by tests; **not** a quality model |
| `civic_text_b0/<version>/` | manifest + model card only | B0 classifier; `weights.npz` and `vocab.json` are gitignored (rebuild on Kaggle or locally) |
| `fusion_calibrator/<version>/` | yes (tiny JSON) | Calibrated fusion weights (+ model card) |
| `datasets/synthetic_v1/` | manifest only | Regenerable synthetic dataset (`python -m ai.training.src.build_dataset`) |
| `b1_experiments/<encoder>/` | report JSON | Optional B1 results |

All datasets/models here are **synthetic-data artifacts**. See each `MODEL_CARD.md`.
