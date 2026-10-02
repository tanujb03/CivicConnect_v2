# Fusion calibrator 0.1.0+b22811b6

> SYNTHETIC-DATA calibration; not a real-world accuracy claim.

- Weights: bias -13.601669, semantic 0.421274, geospatial 7.903118, temporal 1.501159, category 7.277169
- Semantic signal fitted on: **lexical**
- Validation metrics: `{"n_train_gated": 3398, "n_val_gated": 849, "val_positive_rate": 0.47, "val_auc_roc": 0.9879, "val_at_policy_duplicate_threshold": {"threshold": 0.8, "precision": 0.9799, "recall": 0.8571, "f1": 0.9144, "tp": 342, "fp": 7, "fn": 57}, "val_best_f1_threshold": {"threshold": 0.49, "precision": 0.953, "recall": 0.9649, "f1": 0.9589, "tp": 385, "fp": 19, "fn": 14}, "brier": 0.0433, "val_logloss": 0.1757, "l2": 0.001, "semantic_weight_note": null}`

## Limitations
- Fitted on SYNTHETIC pairs whose duplicate/non-duplicate construction encodes our own assumptions.
- Weights are constrained non-negative (each signal is monotone); L2 strength chosen by validation log-loss.
- Lexical semantic signal is mono-lingual: cross-language duplicates need embeddings (re-fit with --semantic-mode provider).
- Thresholds in fusion_policy.v1.json are not tuned on real data unless status is calibrated_real; treat scores as ranking aids requiring human confirmation.
