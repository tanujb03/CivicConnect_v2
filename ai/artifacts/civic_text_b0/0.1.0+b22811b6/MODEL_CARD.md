# Model card — civic_text_b0 0.1.0+b22811b6

> **SYNTHETIC-DATA MODEL.** Trained only on template-generated reports. Do not quote its metrics as real-world accuracy.

## What it is
- Kind: `tfidf_char_ngram_logreg` (character n-gram TF-IDF + multinomial logistic regression, numpy inference)
- Labels: 27 subcategories (`category/subcategory`), taxonomy `1.0.0-draft` (DRAFT_REQUIRES_REVIEW)
- Vectoriser: `char_wb` n-grams [2, 4], 12536 features, normaliser `civic-norm/1`
- Calibration: temperature scaling, T=0.55
- Intended use: offline/unavailable-provider **fallback** for AI-1 intake, cross-check of the provider answer, evaluation baseline.
- Not intended for: autonomous decisions, severity/priority, any real-world accuracy claim.

## Training
- Dataset: b22811b62f878fc0… (see DATASET_MANIFEST.json); seed 42
- Hyperparameters: {"C": 10.0, "ngram_range": [2, 4], "min_df": 2, "max_features": 30000, "solver": "lbfgs", "seed": 42, "refit_on_trainval": true}
- Git SHA: `14f7686235e5fcf7c1a026a3718a267f0bfd08b5`; created 2026-10-02T18:35:23+00:00; runtime {"python": "3.11.15", "platform": "Linux-6.18.44-fc-v51-x86_64-with-glibc2.39", "kaggle": false, "numpy": "2.4.6", "sklearn": "1.9.1", "scipy": "1.17.1", "pydantic": "2.13.4"}

## Metrics (synthetic validation split; unseen template families)
- val_accuracy: 0.5293
- val_macro_f1: 0.5155
- train_accuracy: 1.0
- val_category_accuracy: 0.6667
- c_sweep_val_macro_f1: {'1.0': 0.4903, '3.0': 0.506, '10.0': 0.5155, '30.0': 0.5111}
- note: val metrics are for the train-only model used for selection/calibration; shipped model refit on train+val

Held-out *test* metrics are produced by `ai/evaluation/run_eval.py` and stored in the evaluation report.

## Limitations
- Trained and evaluated on SYNTHETIC template-generated reports only; metrics do not estimate real-world accuracy.
- Char n-gram model: no cross-lingual transfer; paraphrases that share no characters with training phrases may fail.
- Hindi/Marathi/Hinglish phrasing is hand-written and unreviewed by native speakers.
- Calibration (temperature) was fitted on synthetic validation data; probabilities are optimistic for real text.
- Not suitable as the sole basis for any workflow decision; proposals always require human confirmation.
