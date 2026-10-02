# CivicConnect v2 — `ai/`

AI training, evaluation and production inference for the frozen V1 system design (`docs/CivicConnect_v2_V1_System_Design.md`, §11–14, §37–40, §51A.5/7/8/15, §57–58). **Owner: Tanuj. Backend wiring: with Parth** (see `INTEGRATION_HANDOFF.md`).

> Everything trained or measured here uses **synthetic data**. No result is a real-world accuracy claim. Provider (OpenAI) code paths have **not** been run live from the authoring environment.

## Layout (per `docs/COMMON_DIRECTORY_STRUCTURE.md`)
```
ai/
├── inference/          PRODUCTION adapters — importable by the FastAPI backend (pydantic + numpy + httpx only)
│   ├── service.py        AIService facade (single entry point)
│   ├── schemas.py        Pydantic models mirroring 51A.5/7/8/15 (+ additive fields)
│   ├── provider.py       AIProvider protocol · providers/{openai_provider,fake}.py
│   ├── intake/ fusion/ triage/ resolution/ analytics/ copilot/   AI-1 … AI-6
│   ├── local/            numpy-only B0 classifier loader + shared featurizer
│   ├── prompts.py        versioned prompts + JSON schemas
│   ├── config/           taxonomy.v1.json (+TAXONOMY.md), triage_rules, fusion_policy, ai_policy
│   └── tests/            unit/schema/fixture/smoke tests
├── training/           Kaggle notebooks + scripts (NEVER imported by inference)
├── evaluation/         datasets (synthetic), metrics, run_eval.py, reports, regression floors
└── artifacts/          generated models/data — large files gitignored; manifests/cards/fixtures tracked
```
`ai/pyproject.toml` ships **only** `ai.inference` (`pip install ./ai`); training/evaluation cannot be imported by the backend.

## Capability strategy (no separate model per capability)
| | Approach | Trained here? |
|---|---|---|
| AI-1 intake | provider multimodal structured output → taxonomy validation → local B0 cross-check; **local B0 fallback** + manual-entry floor | B0 (TF-IDF char n-gram + logistic regression, numpy inference) |
| AI-2 fusion | deterministic gate (category/radius/window) → semantic (embeddings if available, else lexical) + geo + time + category → calibrated logistic score | weights only (synthetic pairs, non-negative) |
| AI-3 triage | deterministic priority/SLA (§36); AI *recommends* severity (bounded, never lowers safety-critical) | no |
| AI-4 resolution | provider multimodal comparison; **flag-only**, `autonomous_closure_allowed=False`. Deterministic baseline evaluated on synthetic scenarios (`evaluation/datasets/resolution_v1`, `eval_resolution.py`): it flags every citizen-reported failure but never reads note text or pixels; vision path **not evaluated** (no before/after images exist) | no |
| AI-5 analytics | backend facts → validated explanation (numbers verified, template fallback). Reference facts (hotspots, unusual growth, recurrence, SLA risk, geographic concentration, incidents) in `evaluation/analytics_facts.py`; guard rails evaluated with scripted providers (`eval_analytics.py`) — a real LLM's wording is **not** evaluated | no |
| AI-6 copilot | whitelisted read-only tools, scope enforced, answer/citation grounding; no DB credentials | no |

## Hybrid data strategy (real public + synthetic)
Synthetic data is **not** the only source. Real public datasets are acquired *outside git*, prepared into a canonical schema through
explicit, versioned taxonomy mappings, and evaluated on **separate tracks** (`synthetic`, `real_holdout`, `hybrid`, plus descriptive statistics). Synthetic data covers
multilingual text, code-mixing, edge cases and fixtures; real data supplies realism, holdout evaluation and geo/temporal behaviour. **No real data has been downloaded yet**
and no source's licence is verified. See `training/src/data_sources/README.md` for dataset cards, the capability matrix (what each dataset can/cannot support), the
licence status and the workflow. Reports always state their provenance and what may be claimed.

**Indian sources (extension):** the genuinely *real* Indian sources are visual: the Mumbai/Nashik road-surface set (Mendeley `tj2m7zz4rg`, priority), RDD2022 and RDD2020 India, and BharatPotHole (licence pending) — potholes map to `roads/pothole`, no new taxonomy categories; IIIT-H IDD is future-only. **BMC Mumbai** (`bmc_mumbai`) is a large *synthetically generated* Mumbai/BMC-structured civic dataset (per the Kaggle competition information): it is used for pipeline/stress/leakage testing under a default-deny column-role policy and is **never** real-world validation, official BMC data, or pooled with real or project-synthetic results. Synthetic data remains the only source of Hindi/Marathi/Hinglish text, and there is no real before/after resolution evidence anywhere. **Datasets are processed in place on Kaggle** (`/kaggle/input`, notebook `05_kaggle_real_data_profile_evaluate`): nothing is downloaded locally or committed. Licences accepted as verified by the owner on 2026-10-02: BMC (CC BY 4.0, synthetic), Mumbai/Nashik v2 (CC BY 4.0), RDD2022 (applied as the stricter CC BY-SA 4.0) and RDD2020 (CC BY-NC 3.0, non-commercial only); BharatPotHole stays UNVERIFIED. A publishable real-world claim still needs enough annotated held-out rows and a profiled, mapped result — none exists yet. See `training/src/data_sources/README.md`, `TASK_MATRIX.md` and `BMC_COLUMN_POLICY.md` there.

## Demo city (design §58) — synthetic
`ai/evaluation/datasets/demo_city_v1/` is the seeded **synthetic** city the demos run on: 10 wards, 8 departments, 560 Civic Cases with multilingual reports, duplicate groups, recurring problems, hotspots, SLA violations, reopened cases and active incidents, plus planted ground truth. Everything is labelled synthetic (`DEMO-` ids, `"synthetic": true`). Build/verify with `python -m ai.training.src.build_demo_city`, evaluate with `python -m ai.evaluation.eval_demo_city`. See its `README.md`.

## Quick start
```bash
pip install -e "ai[training,dev]"
python -m pytest ai -q -rs                       # all tests runnable offline
python -m ai.training.src.build_dataset --out ai/artifacts/datasets/synthetic_v1 --eval-out ai/evaluation/datasets
python -m ai.training.src.train_text_classifier --data ai/artifacts/datasets/synthetic_v1 --out ai/artifacts/civic_text_b0
```
```python
from ai.inference.service import AIService
from ai.inference.schemas import IntakeRequest
ai = AIService.from_env({"AI_LOCAL_CLASSIFIER_PATH": "ai/artifacts/civic_text_b0/<version>"})   # no provider needed
print(ai.analyze_intake(IntakeRequest(text="सड़क पर बड़ा गड्ढा है")).proposal)
```
Kaggle: see `training/README.md`. Backend: see `INTEGRATION_HANDOFF.md`. Taxonomy: `inference/config/TAXONOMY.md` (**draft — needs Tanuj + Parth review before DB seeding**).

## Current measured results (synthetic, held-out template families; see `evaluation/reports/`)
| System | Result | Notes |
|---|---|---|
| B0 local intake | category 0.616, subcategory 0.546, macro-F1 0.522, ECE 0.063 (216 held-out rows; re-measured 2026-10-02 after the native-speaker phrase corrections) | 5-fold family-grouped CV: category 0.674 ± 0.079, subcategory 0.566 ± 0.100 — **weak on unseen wording by design of the test**; fallback only |
| Fusion (calibrated, lexical) | AUC 0.984, gate recall 1.0 | distance dominates on synthetic pairs; lexical semantic weight is ~0 → provider embeddings needed |
| Fusion (uncalibrated prior) | AUC 0.930 | for comparison |
| Provider intake / embeddings / transcription | **not run** | needs credentials + validated model IDs |
| B1 encoder | **not run** | needs Kaggle (GPU/Internet) |

## Test status (last run: 339 passed, 3 skipped, ~60 s)
| Category | Tests | Status |
|---|---|---|
| **Executed offline, passing** | 339: taxonomy integrity, schemas/contract shapes, featurizer/language, local classifier + artifact validation, triage, intake (incl. all fallbacks), OpenAI provider via **mock transport**, fusion, resolution, analytics grounding, copilot safety, service smoke, production-separation, dataset generator/splits, B0 trainer (sklearn↔numpy parity), fusion calibrator, B1 *pipeline logic* (fake encoder), evaluation metrics/harness/regression floors, **real-data architecture** (source cards + licence/terms gate, canonical schema, mapping layer, adapters, Socrata/figshare clients via mock transport, pairs, splits, hybrid guards, output-path/git hygiene, CLI, evaluation tracks and claim policy — all on invented *format fixtures*, no real data), notebooks (structure + **end-to-end execution of all four** — notebook 02 with a CI-only fake encoder, notebook 04 on format fixtures) | ✅ |
| **Require Kaggle (GPU / Internet / sentence-transformers)** | `training/tests/test_b1_logic.py::test_b1_with_a_real_sentence_encoder` (`-m requires_kaggle`, `RUN_B1_TESTS=1`) and the real B1 notebook run | ⏭ skipped here |
| **Require provider credentials** | `inference/tests/test_live_provider.py` (`-m requires_provider`): live embeddings + live structured intake; plus `run_eval --system provider/hybrid` and fusion `--semantic-mode provider` | ⏭ skipped here — OpenAI path **never run live** |
