# Kaggle runbook — AI training & experiments

Everything here is **synthetic-data** work (see `../evaluation/datasets/DATASET_CARD.md`). Notebooks are thin wrappers; the logic lives in `ai/training/src/` and is unit-tested. Production inference (`ai/inference/`) never imports anything from this folder.

| Notebook | Purpose | Accelerator | Internet | Time | Blocking? |
|---|---|---|---|---|---|
| `01_b0_text_classifier_kaggle.ipynb` | **B0**: build dataset → train TF-IDF char n-gram + LogReg → evaluate → 5-fold CV → package | none (CPU) | **Off** | ≈2–3 min | **Yes — the main deliverable** |
| `03_fusion_calibration_kaggle.ipynb` | AI-2 combined-score calibration (lexical; optional provider-embedding mode) | none | Off (On + secret for embedding mode) | <1 min | Needed for calibrated fusion |
| `04_real_data_prepare_evaluate_kaggle.ipynb` | Real public data: profile → prepare → pairs → real-data evaluation (terms-gated; aggregates-only bundle) | none | On (Socrata) or attached dataset | minutes | No — run after datasets are chosen |
| `05_kaggle_real_data_profile_evaluate.ipynb` | Indian datasets read **in place** from `/kaggle/input`: BMC (synthetic) + Mumbai/Nashik, RDD2022/2020 India, BharatPotHole — profile → audits → readiness; aggregates-only bundle | none | Off is fine | minutes | Run per attached dataset |
| `02_b1_encoder_experiment_kaggle.ipynb` | **B1** (optional): frozen multilingual encoder + LogReg vs B0 | GPU T4/P100 | **On** (downloads encoder) | ≈5–10 min | **No** |

## 1 · Get the code onto Kaggle (pick one)

**A. Kaggle Dataset (recommended; works with Internet off)**
```bash
# from the repo root: ship only the code (no generated data/weights)
zip -r civicconnect-ai-src.zip ai -x "ai/artifacts/datasets/*" "ai/artifacts/civic_text_b0/*" "*/__pycache__/*" "*.pyc"
```
Kaggle → *Datasets → New Dataset* → upload the zip (it unpacks to `/kaggle/input/<name>/ai/...`). In each notebook: *Add Input → Your Datasets*. The bootstrap cell finds `ai/inference/schemas.py` anywhere under `/kaggle/input` and copies it to `/kaggle/working/repo`.

**B. Git clone** — Internet **On**; set an environment variable/secret `CIVIC_GIT_URL` (for a private repo embed a token via a Kaggle Secret; never paste tokens into the notebook).

## 2 · Run

1. *Notebooks → New Notebook → File → Import Notebook* → upload the `.ipynb` (or paste cells). Attach the dataset from step 1.
2. Settings per the table above (Accelerator / Internet). Python 3.11+ images are fine.
3. **Run All.** The first code cell prints `repo`, `work` and Python version. Required packages (numpy, scipy, scikit-learn, pydantic, httpx) normally ship with Kaggle; missing ones are pip-installed automatically.
4. Notebook 01 prints a hash check against `ai/evaluation/datasets/manifest.v1.json` (`OK: dataset reproduced identically…`). A mismatch is a warning (different Python minor version), not an error — the evaluation set is read from the repo, so reported metrics stay comparable.

## 3 · What you get (download from the notebook *Output* tab)

| File | Contents |
|---|---|
| `civic_b0_handoff_<version>.zip` (01) | `civic_text_b0/<version>/{manifest.json, weights.npz, vocab.json, MODEL_CARD.md}`, `reports/intake_b0_local.{json,md}`, `datasets/synthetic_v1/DATASET_MANIFEST.json` |
| `civic_fusion_weights.zip` (03) | `fusion_calibrator/<version>/{fusion_weights.json, MODEL_CARD.md}` (+ `fusion_calibrator_embedding/` if provider mode ran) |
| `civic_b1_report.zip` (02) | `b1_experiments/<encoder>/b1_report.json` |

Unzip into the repo:
```bash
unzip civic_b0_handoff_*.zip -d ai/artifacts/            # -> ai/artifacts/civic_text_b0/<version>/ ...
unzip civic_fusion_weights.zip -d ai/artifacts/          # -> ai/artifacts/fusion_calibrator/<version>/
python -m pytest ai -q -rs                               # regression floors now run against the new artifact
```
`weights.npz` / `vocab.json` are gitignored (large). Commit only the manifests, model cards and reports (they are un-ignored). Point the backend at the artifact with `AI_LOCAL_CLASSIFIER_PATH=ai/artifacts/civic_text_b0/<version>` and `AI_FUSION_WEIGHTS_PATH=ai/artifacts/fusion_calibrator/<version>`.

## 4 · Reproduce locally (no Kaggle)
```bash
pip install -e "ai[training,dev]"          # or: pip install numpy scipy scikit-learn pydantic httpx pytest
python -m ai.training.src.build_dataset --out ai/artifacts/datasets/synthetic_v1 --eval-out ai/evaluation/datasets
python -m ai.training.src.train_text_classifier --data ai/artifacts/datasets/synthetic_v1 --out ai/artifacts/civic_text_b0
python -m ai.training.src.train_fusion_calibrator --data ai/artifacts/datasets/synthetic_v1 --out ai/artifacts/fusion_calibrator
python -m ai.evaluation.run_eval --task intake --system local --artifact ai/artifacts/civic_text_b0/<version>
python -m ai.evaluation.run_eval --task fusion --fusion-weights ai/artifacts/fusion_calibrator/<version>
```

## 5 · Optional: provider-backed runs (need credentials — **not run by the authoring session**)
Set `OPENAI_API_KEY` (Kaggle: *Add-ons → Secrets*) and model IDs **after validating them against the provider's current catalogue** (design §30/§64):
```bash
AI_INTAKE_MODEL=<id> python -m ai.evaluation.run_eval --task intake --system provider   # LLM path on the same held-out set
AI_INTAKE_MODEL=<id> python -m ai.evaluation.run_eval --task intake --system hybrid --artifact <b0-dir>
AI_EMBEDDING_MODEL=<id> python -m ai.training.src.train_fusion_calibrator --data … --out … --semantic-mode provider
```
Without credentials these exit with code 2 and `SKIPPED` — no numbers are fabricated.

## 6 · Reading the results honestly
* B0 is evaluated on **unseen template families and place names**, but the data are generated by the same process as training. Treat the numbers as a regression/ablation signal, not accuracy.
* Each class has only 3 training phrases per language (+1 when refit on train+val). B0 therefore generalises poorly to genuinely new wording — expected, and the reason the provider path is primary and B0 is a fallback/cross-check.
* Run the 5-fold CV cell for a variance estimate; one held-out family per class gives wide intervals.
* Fusion scores are dominated by distance on synthetic pairs (duplicates have small GPS jitter by construction).

## 6b · Real public data
See `src/data_sources/README.md` and notebook 04. Real data never enters the repo; outputs of that notebook are aggregate statistics only. The Indian-dataset layer (BMC Mumbai, RDD2020/2022 India, BharatPotHole, Mumbai/Nashik) is driven by the CLI described in that README (`profile bmc_mumbai`, `profile-images`, `prepare …`, `leakage-audit`); use notebook `05_kaggle_real_data_profile_evaluate.ipynb` to run it on Kaggle against datasets attached under `/kaggle/input` (nothing is downloaded; aggregates-only bundle).

## 7 · Training code layout
```
src/synthetic/    lexicon_*.py (hand-written phrases) · frames.py · noise.py · generator.py
src/build_dataset.py            deterministic dataset + manifest (hashes)
src/train_text_classifier.py    B0 (+ parity check numpy vs sklearn)
src/train_encoder_head.py       B1 (needs sentence-transformers)
src/train_fusion_calibrator.py  AI-2 weights (non-negative, L2 by val log-loss)
src/artifact_writer.py          writes civic-text-classifier/1 artifacts
src/data_sources/               real-data cards, adapters, mappings, column-role policy, leakage audits, downloaders, pairs, hybrid assembly (see its README)
src/make_fixture_artifact.py    tiny committed fixture for tests
notebooks/                      thin Kaggle notebooks
tests/                          generator, trainer, calibrator, notebooks (incl. slow end-to-end execution)
```
