# Handoff: cloud session → local Claude Code session (AI/ML track)

You are a Claude Code session running **on Tanuj's laptop**. Until now the AI/ML track was driven from a cloud session that had **no GPU, no real API keys, no Kaggle access and no way to call Gemini/Groq**. You do have those (Tanuj's machine, RTX 4050, his `.env`). Read this file fully, then `docs/RUNBOOK_ML.md`, then act. Date of handoff: 3 October 2026.

## 1 · Who, what, when
- **User:** Tanuj Vivek Bhide (GitHub `tanujb03`, bhidetanuj@gmail.com). Owns the **AI/ML track** of *CivicConnect v2*, a hackathon project by Indian students. Teammates: Parth (backend), Krrish + Vedant (frontends). Use they/them for anyone whose pronouns are not stated.
- **Everything must be FREE** (students, no credits; there is no OpenAI key). Free stack: Gemini + Groq free tiers, local ONNX models, browser Web Speech API. Full audit: `docs/FREE_STACK_PROPOSAL.md`.
- **Hackathon quality matters.** Tanuj explicitly does not want only "short synthetic lines": real fine-tuned models, honest evaluation, a strong demo.
- **Deadlines** (`docs/TEAM_INTEGRATION_RULES.md`): 3–4 Oct integration with Parth; 5 Oct finishing + PPT; **6 Oct Innovibe submission**; 6–7 Oct Hacksphere.
- **Be autonomous.** Tanuj is often busy and prefers you to keep driving, ask only for what truly needs them (keys, accounts, writing Hindi/Marathi, browser steps), and give exact, ordered instructions. Keep chat answers short; findings go in docs/reports.
- Branch: work on **`tanuj`** (never push to `main` unless Tanuj says "merge"). `main` was last merged at `edcd63d`; `tanuj` is several commits ahead of it (see §9). Commits are authored as Tanuj Vivek Bhide <bhidetanuj@gmail.com>; end commit messages with the attribution trailers your harness specifies.

## 2 · Frozen things: do not change
- `docs/CivicConnect_v2_V1_System_Design.md`, `docs/IMPLEMENTATION_PLAN_*.md`, `docs/TEAM_INTEGRATION_RULES.md`: frozen sources of truth.
- `ai/inference/**` (the production package, `AIProvider` protocol, schemas, taxonomy, policies). New behaviour is added **outside** it (backend gateway, providers, loaders).
- Frontend apps (`apps/`, `packages/`) are not your scope.
- Never describe BharatPotHole's licence as CC BY-NC-SA (that is the code repo's); its data card stays `UNVERIFIED` and the notebook has `USE_BHARATPOTHOLE`. Other licences were accepted as verified by Tanuj (BMC CC BY 4.0, Mumbai/Nashik v2 CC BY 4.0, RDD2020 CC BY-NC 3.0 non-commercial, RDD2022 applied as CC BY-SA 4.0).
- Never write secrets into the repo, chat or notebooks. `.env` is gitignored; show key *names* only.

## 3 · The six AI capabilities (what the product does)
| | capability | how |
|---|---|---|
| AI-1 | multimodal intake (text/voice/image → category, subcategory, severity suggestion, summary) | cloud multimodal LLM with JSON schema → taxonomy validation → local classifier cross-check; local fallback; manual floor |
| AI-2 | duplicate fusion | deterministic gate (category/radius/window) → semantic similarity (local embedder) + geo + time + category → calibrated logistic score |
| AI-3 | triage | **deterministic rules set priority/SLA**; the LLM may only suggest severity (never lowers safety-critical) |
| AI-4 | resolution review | flag-only (never auto-rejects) |
| AI-5 | analytics explanation | deterministic facts; LLM prose must be number-grounded |
| AI-6 | copilot | LLM planner + whitelisted, role-scoped tools |

## 4 · The eight model components (state at handoff)
| | component | state | what finishes it |
|---|---|---|---|
| M1 | Gemini (cloud, free) | adapter + mock tests; **never called live** | `live_check` green |
| M2 | Groq Whisper (cloud STT) | same | `live_check --audio` prints a transcript |
| M3 | B0 char-n-gram LR classifier | trained on synthetic template data; ~0.62 category / 0.55 subcategory held-out; last fallback | nothing |
| M4 | fusion calibrator | trained on synthetic pairs (lexical), distance dominates | recalibrate with M7 (`--semantic-mode local`) |
| M5 | YOLOv8 road-damage detector (D00/D10/D20/D40) | pipeline tested on invented data; **not trained** | notebook 06 on Kaggle (overnight) or local GPU |
| M6 | fine-tuned multilingual-e5 27-label classifier | pipeline + export + backend runtime proven on a tiny random model; **not trained** | corpus → notebook 07 |
| M7 | multilingual-e5 embedder (cross-language duplicates) | same as M6 | notebook 07, then recalibrate M4 |
| M8 | browser Web Speech API | frontend job (snippet in `ai/INTEGRATION_HANDOFF.md` §16) | Krrish/Vedant |

Honest limits to keep in every claim: only M3/M4 are truly trained and only on synthetic data; M1/M2/copilot unverified live; M6/M7 will learn from LLM-written synthetic text (the team-written **gold set** is the real yardstick); no free source of real Indian-language complaint narratives exists (the 311 datasets have category/descriptor only, no narrative text); AI-4's image part cannot be evaluated (no before/after images); real-image metrics do not exist until M5 is trained.

## 5 · Architecture you will touch
- `backend/ai_gateway/`: `service.py` (`AIGateway`: intake incl. local-vision merge, fusion with `embedder`, triage, decision with override audit, copilot, `review_resolution`, `explain_analytics`), `deps.py` (`build_default_gateway`: loads `.env`, then text models, `build_ai_service(executor, classifier)`, vision, embedder), `vision.py` (ONNX YOLO), `text_model.py` (`OnnxTextClassifier`, `OnnxEmbedder`, schema `civic-onnx-text/1`, checksum-verified; int8 preferred unless `AI_TEXT_PREFER_INT8=0`), `envfile.py`, `providers/` (`openai_compat.py`, `composite.py` per-task routing, `factory.py`, `live_check.py`).
- Routes: `backend/api/v1/{cases,copilot,analytics}.py` (`POST /analytics/explain` is additive); error envelope in `backend/core/exceptions.py`.
- `OnnxTextClassifier` is a drop-in for `LocalTextClassifier` (only `predict()`, `model_name`, `model_version`, `label_ids` are used), so `AIService(classifier=...)` works without touching frozen code.
- Env (names only; see `.env.example`): `GEMINI_API_KEY`, `GROQ_API_KEY`; model ids come **only** from env: `AI_INTAKE_MODEL`, `AI_ANALYTICS_MODEL`, `AI_COPILOT_MODEL`, `AI_EMBEDDING_MODEL`, `AI_TRANSCRIPTION_MODEL`; routing/throttling `AI_ROUTES`, `AI_<BACKEND>_RPM`, `AI_<BACKEND>_STRUCTURED`, `AI_<BACKEND>_BASE_URL`; local models `AI_TEXT_ONNX_PATH`, `AI_EMBED_ONNX_PATH`, `AI_VISION_ONNX_PATH`, `AI_LOCAL_CLASSIFIER_PATH`, `AI_FUSION_WEIGHTS_PATH`, `AI_FUSION_EMBEDDING_WEIGHTS_PATH`. Never hard-code model ids; copy them from `live_check --list-models`.
- Training: `ai/training/src/text_corpus/{spec,validate,generate,build}.py` (972 cells = 27 labels × 4 languages {en, hi, mr, hi-Latn} × 9 styles, k=12 → ~11.7k raw items; resumable shards; validation of script/PII/duplicates; group-safe split stratified by (label, language); gold CSV from the team), `ai/training/src/text_model/{train,export,runtime}.py`, `ai/training/src/train_fusion_calibrator.py`, `ai/training/src/vision/`, notebooks `06_road_damage_detector_kaggle.ipynb` and `07_text_models_m6_m7_kaggle.ipynb` (both `SMOKE = True` by default; env hooks `CIVIC_CORPUS_DIR`, `CIVIC_TEXT_MODEL`, `CIVIC_TEXT_PREFIX`, `CIVIC_TEXT_VERSION`, `CIVIC_PATHS_JSON`, `CIVIC_YOLO_MODEL`, `CIVIC_YOLO_DEVICE`).
- Evaluation: `ai/evaluation/` (`run_eval.py`, `eval_demo_city.py`, `classifiers.py::load_classifier` accepts a B0 folder **or** an M6 ONNX folder, regression floors in `regression_floors.json`, reports). Demo city: `ai/evaluation/datasets/demo_city_v1`.
- Preflight: `python -m ai.training.src.doctor` (names only, never values).

## 6 · Design decisions and why (so you do not re-litigate them)
- Rules decide priority; LLMs only propose. Every AI output carries source/model/warnings; degradations are visible in `warnings`, never silent.
- Splits are group-safe everywhere (RDD index blocks, BharatPotHole source video, LLM request groups); RDD2022 (Kaggle YOLO copy) class ids are decoded from evidence by matching boxes with RDD2020 VOC (purity ≥ 0.97, ≥ 200 pairs), never guessed.
- Template rows only go to train/val; the original template test families stay the untouched `intake_eval.v1`; the gold set is evaluation-only.
- Embedding fusion reports `FUSION_UNCALIBRATED_PRIOR` until recalibrated with M7; this is on purpose.
- Gemini/Groq free tiers may use prompts for product improvement: demo/synthetic data only. Free-tier limits could not be checked from the cloud (vendor pages unreachable): treat them as unknown and let `generate` be resumable.
- Bhashini was **not** implemented (its docs could not be verified); only add an adapter if its documentation can be read and verified.

## 7 · Your job, in order (details and commands: `docs/RUNBOOK_ML.md`)
1. Get the repo working: Python 3.11+, venv, `pip install -r backend/requirements.txt`, `pip install -e "ai[training,dev]"`, CUDA torch + `transformers onnx onnxruntime tokenizers ultralytics`; run `python -m ai.training.src.doctor`; run the tests (`python -m pytest ai backend -q`; expect ~750 passed, 3 skipped, ~2.5 min).
2. Have Tanuj create `.env` (repo root) themself; **do not ask them to paste keys**. Then `live_check --list-models`, set the model ids with them, run `live_check` (+ `--image`, + `--audio` with a 5 s Marathi/Hindi clip). This is the first-ever live proof of M1/M2; if a backend misbehaves (structured output, vision, rate limits) fix the adapter under `backend/ai_gateway/providers/` and add a test.
3. Gold set: `build --gold-template`; Tanuj writes ~100–200 per language in their own words (UTF-8 CSV).
4. Corpus: `generate --limit 40`, inspect shards for quality (Hindi/Marathi script, register, no PII, label fidelity), tune `spec.py`/`validate.py` if poor, full run (resumable), `build` with `--templates ai/artifacts/datasets/synthetic_v1` (regenerate with `python -m ai.training.src.build_dataset` if absent) and `--gold`.
5. Notebook 07 smoke → full (local RTX 4050: e5-small batch 32, e5-base batch 16 on 6 GB; or Kaggle). Unzip artifacts into `ai/artifacts/civic_text_m6/<ver>` and `ai/artifacts/civic_embed_m7/<ver>`; evaluate: `python -m ai.evaluation.run_eval --task intake --system local --artifact <folder>`; if M6 beats B0 on held-out + gold, make it the default in docs.
6. Recalibrate fusion: `python -m ai.training.src.train_fusion_calibrator --data ai/artifacts/datasets/synthetic_v1 --out ai/artifacts/fusion_calibrator --semantic-mode local --embed-onnx ai/artifacts/civic_embed_m7/<ver>`; set `AI_FUSION_EMBEDDING_WEIGHTS_PATH`; optionally add an embedding-mode cross-language duplicate evaluation on demo-city.
7. Notebook 06 (M5): Kaggle, four datasets attached (RDD2020 copy, `aliabdelmenam/rdd-2022`, `surbhisaswatimohanty/bharatpothole`, Mumbai/Nashik copy), GPU + Internet on; smoke first, then full overnight; local alternative via `CIVIC_PATHS_JSON` + `CIVIC_YOLO_DEVICE=0`. Put `best.onnx` + `model_card.json` under `ai/artifacts/road_damage/road_damage/` and set `AI_VISION_ONNX_PATH`.
8. Integration with Parth (3–4 Oct): `ai/INTEGRATION_HANDOFF.md` (§§11–16) is the contract. Run the API (`uvicorn backend.main:app --reload`), exercise intake/fusion/triage/copilot/analytics with the live providers and the local models; fix gaps.
9. Keep docs honest: after each milestone update `ai/README.md` (model-state table, measured results), `ai/INTEGRATION_HANDOFF.md`, and this file's §4. Commit on `tanuj` with focused messages; push when green; open a PR only if asked.

## 8 · Conventions
- Match the surrounding code (dense, typed, short docstrings; ruff line length 130, target py311). Run `ruff check` on touched files; the pre-existing errors in `backend/tests/test_phase_c.py` / `test_phase_d.py` are not yours.
- Add tests for behaviour you add; the notebook tests (`ai/training/tests/test_notebooks.py`) cap notebook cells at 200 lines.
- Prefer ONNX/CPU-friendly serving (`onnxruntime`, `tokenizers`); training stays under `ai/training` and is never imported by `ai.inference`.
- Windows: use UTF-8 explicitly when reading/writing text (all current code does; a UTF-8 BOM and CRLF in `.env` and the gold CSV are handled and tested).
- Report outcomes faithfully (failing tests, skipped steps, unverified claims). Do not claim real-world accuracy from synthetic data.

## 9 · State at handoff
- Last pushed commit on `tanuj`: `27744a9` (M6/M7 text models, notebook 07, ONNX-aware evaluation loader, `docs/RUNBOOK_ML.md`, handoff §16). A later commit adds this file, `ai/training/src/doctor.py` (+tests), BOM/CRLF fixes in `backend/ai_gateway/envfile.py` and `ai/training/src/text_corpus/build.py`, and README updates; check `git log` to confirm it is there.
- Tests at last full run: **750 passed, 3 skipped** (`python -m pytest ai backend -q`). The 3 skips need live OpenAI or `sentence-transformers`.
- Not done anywhere yet: live Gemini/Groq calls, any real GPU training (M5/M6/M7), gold set, corpus generation, fusion recalibration with embeddings, M6 evaluation, Bhashini. Not possible: AI-4 vision evaluation. Blocked: rewriting authorship of six old commits (needs history rewrite the owner has not authorised).
- Reports to regenerate when models change: `ai/evaluation/reports/`.

## 10 · First message to Tanuj (suggested)
Run the doctor, say what is missing, then walk them through `.env` creation and `live_check --list-models`. Keep going from there without waiting to be asked.
