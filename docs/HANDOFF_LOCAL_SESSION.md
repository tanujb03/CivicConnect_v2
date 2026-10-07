# Handoff: cloud session → local Claude Code session (AI/ML track + backend)

You are a Claude Code session running **on Tanuj's laptop**. Until now the AI/ML track was driven from a cloud session that had **no GPU, no real API keys, no Kaggle access and no way to call Gemini/Groq**. You do have those (Tanuj's machine, RTX 4050, his `.env`). Read this file fully (the **backend** is §10), then `docs/RUNBOOK_ML.md` for the ML steps, then act. Two workstreams: (A) ML models: §3–9 and the runbook; (B) the backend that was audited and implemented in the cloud session: §10 and `docs/BACKEND_AUDIT.md`. Date of handoff: 3 October 2026.

> **Update 2026-10-04 (supersedes parts of §1, §2, §10 below):** Parth has no unpushed work and moved to the frontend; Tanuj and the Claude sessions now own `backend/`, `ai/`, `alembic/`, `infra/` and `packages/api-client`, so there is no "coordinate with Parth before editing `backend/`" step. Frozen docs may change when necessary, but every deviation is logged in `docs/V1_CHANGE_LOG.md`. Working rules (worktree lanes, merge protocol, ports, drives) are in `CLAUDE.md`, which wins over this file where they differ.

## 1 · Who, what, when
- **User:** Tanuj Vivek Bhide (GitHub `tanujb03`, bhidetanuj@gmail.com). Owns the **AI/ML track** of *CivicConnect v2*, a hackathon project by Indian students. Teammates: Parth (backend), Krrish + Vedant (frontends). Use they/them for anyone whose pronouns are not stated.
- **Everything must be FREE** (students, no credits; there is no OpenAI key). Free stack: Gemini + Groq free tiers, local ONNX models, browser Web Speech API. Full audit: `docs/FREE_STACK_PROPOSAL.md`.
- **Hackathon quality matters.** Tanuj explicitly does not want only "short synthetic lines": real fine-tuned models, honest evaluation, a strong demo.
- **Deadlines** (`docs/TEAM_INTEGRATION_RULES.md`): 3–4 Oct integration with Parth; 5 Oct finishing + PPT; **6 Oct Innovibe submission**; 6–7 Oct Hacksphere.
- **Be autonomous.** Tanuj is often busy and prefers you to keep driving, ask only for what truly needs them (keys, accounts, writing Hindi/Marathi, browser steps), and give exact, ordered instructions. Keep chat answers short; findings go in docs/reports.
- Branch: work on **`tanuj`** (never push to `main` unless Tanuj says "merge"). As of the end of the cloud session **`tanuj` was merged into `main`** (commit `e4b1fe4`, both branches identical): everything described here is on `main` too. Commits are authored as Tanuj Vivek Bhide <bhidetanuj@gmail.com>; **no** `Co-Authored-By` / "Generated with" trailers (see `CLAUDE.md`).

## 2 · Frozen things: do not change
- `docs/CivicConnect_v2_V1_System_Design.md`, `docs/IMPLEMENTATION_PLAN_*.md`, `docs/TEAM_INTEGRATION_RULES.md`: frozen sources of truth.
- `ai/inference/**` (the production package, `AIProvider` protocol, schemas, taxonomy, policies). New behaviour is added **outside** it (backend gateway, providers, loaders).
- Frontend apps (`apps/`, `packages/`) are not your scope (you may READ `apps/admin/src/lib/api.ts`: it is the client the backend contract was checked against). The backend (`backend/`, `alembic/`) IS in scope now, but coordinate with Parth first (§10).
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
1. Get the repo working: Python 3.11+, venv, `pip install -r backend/requirements.txt`, `pip install -e "ai[training,dev]"`, CUDA torch + `transformers onnx onnxruntime tokenizers ultralytics`; run `python -m ai.training.src.doctor`; run the tests (`python -m pytest ai backend -q`; expect ~752 passed, 6 skipped, ~2.5 min).
2. Have Tanuj create `.env` (repo root) themself; **do not ask them to paste keys**. Then `live_check --list-models`, set the model ids with them, run `live_check` (+ `--image`, + `--audio` with a 5 s Marathi/Hindi clip). This is the first-ever live proof of M1/M2; if a backend misbehaves (structured output, vision, rate limits) fix the adapter under `backend/ai_gateway/providers/` and add a test.
3. Gold set: `build --gold-template`; Tanuj writes ~100–200 per language in their own words (UTF-8 CSV).
4. Corpus: `generate --limit 40`, inspect shards for quality (Hindi/Marathi script, register, no PII, label fidelity), tune `spec.py`/`validate.py` if poor, full run (resumable), `build` with `--templates ai/artifacts/datasets/synthetic_v1` (regenerate with `python -m ai.training.src.build_dataset` if absent) and `--gold`.
5. Notebook 07 smoke → full (local RTX 4050: e5-small batch 32, e5-base batch 16 on 6 GB; or Kaggle). Unzip artifacts into `ai/artifacts/civic_text_m6/<ver>` and `ai/artifacts/civic_embed_m7/<ver>`; evaluate: `python -m ai.evaluation.run_eval --task intake --system local --artifact <folder>`; if M6 beats B0 on held-out + gold, make it the default in docs.
6. Recalibrate fusion: `python -m ai.training.src.train_fusion_calibrator --data ai/artifacts/datasets/synthetic_v1 --out ai/artifacts/fusion_calibrator --semantic-mode local --embed-onnx ai/artifacts/civic_embed_m7/<ver>`; set `AI_FUSION_EMBEDDING_WEIGHTS_PATH`; optionally add an embedding-mode cross-language duplicate evaluation on demo-city.
7. Notebook 06 (M5): Kaggle, four datasets attached (RDD2020 copy, `aliabdelmenam/rdd-2022`, `surbhisaswatimohanty/bharatpothole`, Mumbai/Nashik copy), GPU + Internet on; smoke first, then full overnight; local alternative via `CIVIC_PATHS_JSON` + `CIVIC_YOLO_DEVICE=0`. Put `best.onnx` + `model_card.json` under `ai/artifacts/road_damage/road_damage/` and set `AI_VISION_ONNX_PATH`.
8. Integration with Parth (3–4 Oct): **read §10 (Backend) first**: the backend was audited and implemented from the cloud session; tell Parth and agree who edits `backend/`. `ai/INTEGRATION_HANDOFF.md` (§§11–16) is the AI contract. Run the API (`uvicorn backend.main:app --reload`), exercise intake/fusion/triage/copilot/analytics with the live providers and the local models; fix gaps.
9. Keep docs honest: after each milestone update `ai/README.md` (model-state table, measured results), `ai/INTEGRATION_HANDOFF.md`, and this file's §4. Commit on `tanuj` with focused messages; push when green; open a PR only if asked.

## 8 · Conventions
- Match the surrounding code (dense, typed, short docstrings; ruff line length 130, target py311). Run `ruff check` on touched files; the pre-existing errors in `backend/tests/test_phase_c.py` / `test_phase_d.py` are not yours.
- Add tests for behaviour you add; the notebook tests (`ai/training/tests/test_notebooks.py`) cap notebook cells at 200 lines.
- Prefer ONNX/CPU-friendly serving (`onnxruntime`, `tokenizers`); training stays under `ai/training` and is never imported by `ai.inference`.
- Windows: use UTF-8 explicitly when reading/writing text (all current code does; a UTF-8 BOM and CRLF in `.env` and the gold CSV are handled and tested).
- Report outcomes faithfully (failing tests, skipped steps, unverified claims). Do not claim real-world accuracy from synthetic data.

## 9 · State at handoff
- Last pushed commit on `tanuj`: `27744a9` (M6/M7 text models, notebook 07, ONNX-aware evaluation loader, `docs/RUNBOOK_ML.md`, handoff §16). A later commit adds this file, `ai/training/src/doctor.py` (+tests), BOM/CRLF fixes in `backend/ai_gateway/envfile.py` and `ai/training/src/text_corpus/build.py`, and README updates; check `git log` to confirm it is there.
- Tests at last full run: **752 passed, 6 skipped** (3 skips need live OpenAI / sentence-transformers, 3 need `TEST_DATABASE_URL`) (`python -m pytest ai backend -q`). The 3 skips need live OpenAI or `sentence-transformers`.
- Backend: audited and implemented (§10); merged to `main`; 113 backend tests + 3 PostgreSQL/PostGIS tests green in the cloud sandbox. Open items are listed at the end of §10.
- Not done anywhere yet (ML): live Gemini/Groq calls, any real GPU training (M5/M6/M7), gold set, corpus generation, fusion recalibration with embeddings, M6 evaluation, Bhashini. Not possible: AI-4 vision evaluation. Blocked: rewriting authorship of six old commits (needs history rewrite the owner has not authorised).
- Reports to regenerate when models change: `ai/evaluation/reports/`.

## 10 · Backend (Parth's scope): audited, then implemented from the cloud session
**Audit:** `docs/BACKEND_AUDIT.md`. Parth said the backend was done; what was in the repo was a scaffold with mock responses (hard-coded `admin/admin` login, `CC-MOCK-1` cases, empty lists, no migrations, no state machine, no idempotency, passlib+bcrypt5 crashing on first hash). Tell Parth plainly and **coordinate before either of you edits `backend/`**: this branch rewrote models, routers and tests (see "What changed for Parth" below). If Parth has unpushed local work, merge it by hand against these files.

**Now real (all verified by tests; 752 passed in the full suite, plus 3 PostgreSQL+PostGIS integration tests that ran green in the cloud sandbox against PostgreSQL 16 + PostGIS 3.4):**
- Schema = design §34 (`backend/models/`), Alembic `0001` (tables) + `0002` (PostGIS generated `geog` column + GiST index + GIN full-text index; PostgreSQL only). `alembic upgrade head`, `alembic check` (no drift), downgrade/upgrade all verified on real PostGIS. SQLite also works for quick local runs and the unit tests.
- Auth (§51A.2): register/login (JSON)/refresh (rotating, reuse detection)/logout/`auth/me`, bcrypt, access JWT + opaque refresh tokens, login throttle, roles read from the DATABASE (a forged role claim or a demoted user gets nothing). **Deviation:** §51A.2's register has no password but login needs one, so `password` is required; `/auth/token` (OAuth2 form) exists for Swagger "Authorize". OTP login (§41) is NOT implemented.
- Cases (§51A.4): create (server-owned status/priority/SLA/department/ward via the deterministic §36 rules; `client_case_id` dedupe; Idempotency-Key replay), list (filters, `q`, sort, cursor pagination), get (role-shaped), patch (role + state rules, audited overrides with reason), contributors, support/unsupport, reject, reopen, timeline (role-filtered, cursor). Object-level authorization: citizens own/supported cases, field workers assigned cases, operators/managers their department, ward officers their ward, city/system admin all, overlooker aggregates only; invisible cases answer 404.
- State machine (§35) in `backend/services/workflow.py` (the only place that assigns `case.status`): every transition writes an immutable `CaseEvent`, audit rows for rejection/resolution/reopening/verification, and reporter notifications.
- Evidence (§51A.6, §44): upload-init -> PUT signed URL -> complete (size, sha256, magic-byte MIME sniff, extension check), generated object keys, short-lived signed GET, visibility rules, `LocalStorage` (served by the API) and `S3Storage` (MinIO/Supabase/R2 via boto3; **untested against a live server**, boto3 is only in `backend/requirements-s3.txt`).
- Work orders (§51A.9), verification (§51A.10, policy table `VERIFICATION_POLICY`: YES->RESOLVED, NO->REOPENED, STILL_OCCURRING->REOPENED+escalate, PARTIAL->staff decide), notifications (§53, DB rows + Redis stream).
- Map / analytics / incidents / offline sync (§51A.12-14, 16): real queries; `/sync/mutations` is the batch endpoint with APPLIED / ALREADY_APPLIED / REJECTED per mutation, `/sync/changes` cursor stream; incidents with boundary, linked cases, priority bonus, notifications. `/api/v1/health/live` and `/api/v1/health/ready`.
- AI on the database: `backend/ai_gateway/sql.py` (SQL/PostGIS ports; copilot tools and AI-5 facts reuse the demo-city logic over live rows), `AI_GATEWAY_STORE` defaults to `sql` (`demo` = synthetic demo city, no database; the test run pins `demo`, the DB-backed `env` fixture uses `sql`). AI endpoints obey the same object-level rules; a triage decision is applied to the case through the same service; AI-4 flags run after a work order completes / a citizen verifies (staff-only, flag-only); `civic:ai_jobs` worker stores the AI-3 recommendation and AI-2 duplicate relations after a case commits.
- Contract: `backend/openapi.json` regenerated (`python -m backend.scripts.generate_openapi`; a test fails when it goes stale) and a test asserts every §51A endpoint exists. The admin client `apps/admin/src/lib/api.ts` was used as the shape reference (analytics overview, map markers, etc.).

**Run it (Windows PowerShell; needs Docker; from the repository root, with the venv active):**
```powershell
.\scripts\dev\db_up.ps1                   # builds PostGIS 18-3.6 + pgvector (infra/docker/postgres), (re)creates civic-db on port 5433 (named volume) and starts civic-redis
$env:DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5433/civicconnect"   # 5433: a host PostgreSQL service may own 5432
pip install -r backend/requirements.txt
python -m alembic upgrade head
python -m backend.scripts.seed_demo        # reference data + 560 synthetic cases + demo accounts (prints them; password civicconnect-demo)
python -m uvicorn backend.main:app --reload   # http://localhost:8000/docs ; health: GET /api/v1/health/ready (the health routes sit under the API prefix)
```
Parallel sessions use `scripts\dev\new_worktree.ps1` (one worktree, database, Redis DB and port per slot; see `CLAUDE.md` section 4).
Demo logins (password `civicconnect-demo`): `admin@demo.civicconnect.test` (city admin), `operator.road_maintenance@...`, `manager.road_maintenance@...`, `worker.road_maintenance@...`, `ward01@...`, `overlooker@...`, `sysadmin@...`, `citizen001@...` (all `@demo.civicconnect.test`). Real deployments: `python -m backend.scripts.seed_demo --reference-only`, set `ENVIRONMENT=prod` and a private `SECRET_KEY` (startup refuses the dev secret).
Tests: `python -m pytest ai backend -q` (the unit tests ignore `.env`, `DATABASE_URL` and `REDIS_URL` on purpose); PostgreSQL ones: create the test database (`docker exec civic-db psql -U postgres -c "CREATE DATABASE civicconnect_test"`, then `CREATE EXTENSION postgis; CREATE EXTENSION vector;` in it) and run `TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5433/civicconnect_test python -m pytest backend/tests/test_postgres_integration.py`; the live-Redis test uses `TEST_REDIS_URL` (default `redis://localhost:6379/15`) and skips when no Redis answers.

**What changed for Parth (so nobody is surprised):** `backend/models/*` rewritten (UUID string ids, `case_number`, §34 columns; Parth's `Geometry` columns replaced by lat/lon + a DB-generated PostGIS column); `backend/api/v1/*` rewritten except `copilot.py`; `backend/schemas/*` replaced; `backend/core/{config,security,exceptions}.py` extended (security now uses `bcrypt` directly, JWT `typ` claim, `current_user`, `require_capability`); `backend/events/publisher.py` got a 30 s "Redis is down" memory (no 2 s wait per event) and `workers.py` handlers do real work; `test_phase_c.py` (asserted the mocks) removed, `test_phase_d.py` split into `test_events.py` (kept) and the new `test_api_*.py`; committed `__pycache__` removed from git. `infra/` now holds only the Postgres image (`infra/docker/postgres`); there is no backend Dockerfile/compose yet, see below.

**Honest gaps (do next, in this order):**
1. Run the whole thing against the real frontends (`apps/admin`, `apps/citizen`, `apps/overlooker`): set `VITE_API_BASE_URL`, fix any shape mismatch in the backend (the contract is §51A; `apps/admin/src/lib/api.ts` is already aligned). Generate `packages/api-client` from `backend/openapi.json` (not done).
2. `infra/`: Dockerfile + docker-compose (postgis, redis, backend, minio optional) and a Cloudflare Tunnel note from `docs/FREE_STACK_PROPOSAL.md` — not written; docker could not run in the cloud sandbox.
3. Not implemented: OTP/email login (§41), web push delivery, rate limiting beyond the per-process login throttle, malware scanning of uploads, OpenTelemetry tracing, pgvector similarity (embeddings are stored as JSON in `case_embeddings`, not yet populated), voice transcription wiring (AUDIO evidence is passed to the AI service as bytes; Groq Whisper needs the live keys), category suggestion from the local text model when a case is created without a category (it lands in `other/unclassified` for a human).
4. `S3Storage` and Redis workers were not exercised against real services (Redis was only used through mocks and the local sandbox server for smoke checks); analytics are computed in Python over scoped rows (fine for the demo size, move to SQL group-by if cases reach many thousands).
5. `backend/services/analytics.py` imports two pure functions from `ai/evaluation/analytics_reference.py` (hotspots, recurring sites) so dashboard numbers and copilot numbers agree; copy them into the backend if you want the backend deployable without `ai/evaluation`.

## 11 · First message to Tanuj (suggested)
Run the doctor, say what is missing, then walk them through `.env` creation and `live_check --list-models`. In the same first message ask whether Parth has unpushed backend work and remind them to tell Parth the backend was rewritten (§10). Then bring up the backend with the §10 commands (PostGIS + `alembic upgrade head` + `seed_demo` + `uvicorn`) and try the real frontends against it. Keep going from there without waiting to be asked.
