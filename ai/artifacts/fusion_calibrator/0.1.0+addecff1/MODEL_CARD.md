# Fusion calibrator 0.1.0+addecff1

> SYNTHETIC-DATA calibration; not a real-world accuracy claim.

- Weights: bias -13.74788, semantic 0.0, geospatial 8.199886, temporal 1.440794, category 7.292101
- Semantic signal fitted on: **lexical**
- Validation metrics: `{"n_train_gated": 3396, "n_val_gated": 849, "val_positive_rate": 0.47, "val_auc_roc": 0.9809, "val_at_policy_duplicate_threshold": {"threshold": 0.8, "precision": 0.9788, "recall": 0.8095, "f1": 0.8861, "tp": 323, "fp": 7, "fn": 76}, "val_best_f1_threshold": {"threshold": 0.43, "precision": 0.9431, "recall": 0.9549, "f1": 0.9489, "tp": 381, "fp": 23, "fn": 18}, "brier": 0.051, "val_logloss": 0.199, "l2": 0.001, "semantic_weight_note": "semantic weight is ~0: the lexical signal is not informative on synthetic pairs (duplicates use different phrasings). Fit with --semantic-mode provider for embeddings."}`

## Limitations
- Fitted on SYNTHETIC pairs whose duplicate/non-duplicate construction encodes our own assumptions.
- Weights are constrained non-negative (each signal is monotone); L2 strength chosen by validation log-loss.
- Lexical semantic signal is mono-lingual: cross-language duplicates need embeddings (re-fit with --semantic-mode provider).
- Thresholds in fusion_policy.v1.json are not tuned on real data; treat scores as ranking aids requiring human confirmation.
