# AI → Backend hand-off (for Parth)

Status: **Phase A complete (AI/model work + production adapter). Backend wiring: AI gateway implemented against the synthetic demo city (§11); SQL-backed ports are Parth's remaining work.** Everything below is the contract between `ai/inference` and `backend/app/ai`. It implements the frozen design (§11–14, §37–40, §51A.5/7/8/15) and does not change any API.

> **Gate:** do not seed the DB from `ai/inference/config/taxonomy.v1.json` until Tanuj + Parth have reviewed it (`TAXONOMY.md`).

## 1 · Import and packaging
* Package root is `ai.inference`; entry point `ai.inference.service.AIService`. Runtime deps only: **pydantic ≥2, numpy, httpx** (no scikit-learn/torch/pandas; verified by `test_separation.py`, which also checks that importing the service loads none of them).
* Either `pip install ./ai` (ships *only* `ai.inference` + its JSON config; training/evaluation/tests are excluded by `ai/pyproject.toml`) or `COPY ai/ /app/ai/` with `/app` on `PYTHONPATH`.
* Authored/tested on **Python 3.11**; the frozen stack says 3.14 — wheels for numpy/pydantic on 3.14 and pickle-free artifacts make this low-risk but it is **untested**.
* Calls are **synchronous** (HTTP + numpy). Run them in the AI worker (Redis Streams consumer) or `run_in_threadpool`, never directly in an `async def` handler.
* Build once at startup: `ai = AIService.from_env(tool_executor=...)`; `ai.status()` gives a secret-free diagnostic dict (taxonomy status, provider/model IDs, classifier/weights versions).

## 2 · Endpoint ↔ adapter map

| Contract (51A) | Adapter call | Backend must supply | Backend must do with the result |
|---|---|---|---|
| `POST /cases/intake/analyze` | `ai.analyze_intake(IntakeRequest)` → `IntakeResponse` | `text`, `language_hint`, `location`, and **resolved evidence** (`EvidenceInput`: bytes ≤ limits, or a *backend-signed* object-store URL, or a transcript). The adapter never looks up `evidence_ids`. | Persist as `AIAnalysis` (§3). Return `proposal`, `confidence`, `warnings`, `requires_confirmation` (always true). Extra additive fields: `alternatives`, `ai_metadata`, `proposal.{subcategory,suggested_department,transcript,reasons,evidence_refs}` |
| `POST /cases/{id}/fusion/analyze` | `ai.analyze_fusion(FusionRequest)` → `FusionResponse` | Candidate cases from **PostGIS/pgvector** bounded by `ai.fusion.candidate_query_params()` (`radius_m`, `time_window_days`, same category, `max_candidates`). Subject + candidates as `FusionCase` incl. stored `embedding` and `embedding_model` when available | Return `matches[]` with `signals{semantic,geospatial,temporal,visual}` (+ `category`, `signals_available`, `distance_m`, `age_hours`, `semantic_source`) and `recommendation`. Merging stays an authorised, audited action |
| `POST /cases/{id}/triage/analyze` | `ai.analyze_triage(TriageRequest)` → `TriageResponse` | `category`, `subcategory`, canonical `text`, `support_count`, `case_age_hours`, `recurrence_count`, `location_tags` (from your geo layer, e.g. `school`, `hospital`), `incident_active` | Return `recommendation{severity,priority,department,sla_hours,sla_class}`, `confidence`, `reasons`, `warnings`. **No reporter attributes are accepted** (request model forbids extras) |
| `POST /cases/{id}/triage/decision` | *(no AI call)* | The human decision | Store decision + reason; if it differs from the stored AI recommendation write an `AuditEvent` (AI override, §46) |
| `POST /copilot/query` | `ai.copilot_query(CopilotQuery, ActorContext)` → `CopilotResponse` | A `ToolExecutor` (§4) and the authenticated `ActorContext(user_id, role)`. Check role first (§51A.18: Admin, Overlooker scoped) | Return `answer`, `data`, `citations`, `warnings` (+ `tool_calls` for audit) |
| *(hook)* work-order complete / evidence added | `ai.review_resolution(ResolutionReviewRequest)` | Case context, original + resolution evidence, field notes, citizen verification if any | **Flags only.** Store as `AIAnalysis`; surface `unresolved_condition_suspected` / `recommend_verification_request`. State transitions stay server-authoritative; `autonomous_closure_allowed` is a constant `False` |
| *(hook)* analytics summaries (A02, O05) | `ai.explain_analytics(AnalyticsFactSet)` | **Deterministic facts** from your SQL, display-ready (e.g. `value="27%"`) with `ref_type/ref_id` | Show `summary` + `highlights` + `citations`. Numbers are verified against the facts; otherwise a template is returned |
| *(case creation)* | `ai.fusion.embed_texts([...])` → `EmbeddingResult(vectors, model, dimension)` | Canonical text | Store the vector in pgvector **with `embedding_model` and dimension** |

51A has **no endpoint** for AI-4/AI-5/embeddings; they are internal hooks (as in the Tanuj plan). Intake/fusion/triage may be enqueued (`case.ai_requested` → `case.ai.completed`, §23) — the adapter is stateless and idempotent for the same input.

## 3 · Persisting `AIAnalysis` (§12, §34)
Map each response's `ai_metadata` onto the entity:

| `AIAnalysis` column | Source |
|---|---|
| `task_type` | `ai_metadata.task_type` (`intake`, `fusion`, `triage`, `resolution`, `analytics_explain`, `copilot`) |
| `model` / `model_version` | `ai_metadata.model` / `ai_metadata.model_version` (provider model ID, or local artifact version, or fusion-weights version) |
| `prompt_version` / `schema_version` | `ai_metadata.prompt_version` / `ai_metadata.schema_version` (`ai-schemas/1`) |
| `confidence/quality` | response `confidence` (+ `ai_metadata.confidence_basis` explains what it is — a self-reported model estimate, a calibrated *synthetic* probability, or a nominal rules-only marker; never present it as a calibrated real-world probability) |
| `result_json` | `response.model_dump(mode="json")` — includes `source`, `degraded`, `fallback_reason`, `taxonomy_version`, `warnings`, `input_refs` |
| `created_at` | `ai_metadata.created_at` |
| human decision | your triage/intake confirmation flow (§12) |

Store **IDs, not labels** (taxonomy). `taxonomy_version` is inside `ai_metadata`.

## 4 · Copilot `ToolExecutor` you must implement
Protocol: `ai.inference.copilot.tools.ToolExecutor.execute(tool, arguments, *, scope, actor) -> ToolResult(rows, citations, truncated)`.
* Tools (validated Pydantic args, `extra=forbid`; **no SQL/table/column/credential parameters exist**): `search_cases`, `count_cases`, `get_analytic`. See `copilot/tools.py` for filters (`category`, `subcategory`, `status[]`, `unresolved_only`, `severity[]`, `priority[]`, `ward_id`, `ward_label`, `department_id`, `older_than_days`, `created_from/until`, `sort`, `limit≤200`; `group_by`; analytic `name`).
* You must: map tools to **parameterised** queries; resolve `ward_label` ("W18") to a ward the actor may see; enforce RBAC for `actor`/`scope`; return rows containing a `case_id` (or `id`) and matching `Citation(type, id)` entries; raise `ToolPermissionDenied` when not allowed. The orchestrator already overrides any model-supplied ward/department/date outside `scope`, caps rows (50) and tool calls (4), and never leaks executor exception text.
* The model gets **no database credentials**; rows it sees are exactly what your executor returns — return only fields an Admin/Overlooker may see (no citizen PII).

## 5 · Environment variables (add to `.env.example`; **no model IDs are hard-coded**)

| Variable | Meaning |
|---|---|
| `AI_PROVIDER` | `openai` (default when a key is set) or `none` |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL` | secret (never log) / default `https://api.openai.com/v1` |
| `AI_INTAKE_MODEL` | vision-capable model for intake (also fallback for triage/resolution) |
| `AI_TRIAGE_MODEL`, `AI_RESOLUTION_MODEL` | optional per-task overrides |
| `AI_ANALYTICS_MODEL` | analytics explanations (also fallback for copilot) |
| `AI_COPILOT_MODEL` | optional override |
| `AI_EMBEDDING_MODEL` | design suggests `text-embedding-3-small` — **validate against the live catalogue at kickoff (§30/§64)** |
| `AI_TRANSCRIPTION_MODEL` | speech-to-text |
| `AI_REQUEST_TIMEOUT_S` (30), `AI_MAX_RETRIES` (1) | provider HTTP behaviour |
| `AI_LOCAL_CLASSIFIER_PATH` | e.g. `ai/artifacts/civic_text_b0/<version>` (offline fallback for AI-1) |
| `AI_FUSION_WEIGHTS_PATH`, `AI_FUSION_EMBEDDING_WEIGHTS_PATH` | calibrated weights for the lexical / embedding semantic signal (`status`: `calibrated_synthetic`, `calibrated_real`, or the uncalibrated prior; real-data calibration has not been run yet) |

With none of these set the service still works in a **degraded, visible** mode (rules + manual entry).

## 6 · Failure and fallback semantics (acceptance: "failures degrade gracefully and are visible")
Provider problems **never raise**. Check `warnings` (machine code before the colon) and `ai_metadata.{source,degraded,fallback_reason}`:

| `ai_metadata.source` | Meaning | UI suggestion |
|---|---|---|
| `provider` / `provider+rules` | normal | show proposal |
| `local_fallback` | provider failed/unconfigured; local classifier used (`LOCAL_FALLBACK_USED`) | show proposal with "AI assistant degraded" notice, lower prominence |
| `rules` | deterministic only (triage, fusion, resolution) | show reasons; note rules-only |
| `none` | no AI at all (`NO_AI_AVAILABLE`) | **manual categorisation required** (`other/unclassified`, confidence 0) |

Only invalid *input* raises: `pydantic.ValidationError` (→ 422), `InputLimitExceeded` (→ 413/422), `ToolValidationError` (→ 422). Retries: the adapter retries a failed provider call once (429/5xx/transport); additional job-level retry belongs in your Redis consumer. Logs: logger `civicconnect.ai*`, structured `extra={task, outcome, …}`; **no citizen text/media/secrets are logged**.

## 7 · Security and privacy checklist
* `EvidenceInput.url` is forwarded to the provider (which fetches it). Pass **only URLs your backend signed** for private objects; never a user-supplied URL (SSRF, §42/§44). Bytes are held in memory only, excluded from serialisation/repr.
* Provider requests set `store: false` (no provider-side retention by default) — *unverified against the live API*.
* Validate MIME/size/malware **before** calling the adapter (§44); the adapter additionally enforces count/size limits from `config/ai_policy.v1.json`.
* Prompts treat citizen text as untrusted data; protected attributes are never inputs; AI never sets priority/SLA/assignment or closes a case.

## 8 · Test aids for backend tests
`ai.inference.providers.fake.FakeProvider` (scriptable, deterministic, hashed-trigram embeddings), `ai/artifacts/fixtures/b0_tiny/` (150 KB local classifier fixture), `AIService(provider=FakeProvider(...), classifier=..., tool_executor=...)`.

## 9 · What is NOT verified (be explicit in demos)
* The **OpenAI REST path has not been run against the live API** (no credentials/egress in the authoring environment): request shapes follow the documented Responses/Embeddings/Transcription APIs and are covered by mock-transport tests only. Run `pytest ai/inference/tests/test_live_provider.py -m requires_provider -rs` with credentials first.
* Model IDs/availability are unverified.
* All trained/calibrated numbers are on **synthetic data**.

## 10 · Checklist for Parth
- [ ] Review + approve `taxonomy.v1.json` with Tanuj, then seed `Department`/category/SLA from it.
- [x] Department value in API responses: **decided in the gateway** — `department` / `suggested_department` = department *code* exactly as the 51A.8 example (`WATER`); canonical id in additive `department_id` / `suggested_department_id`; decision requests accept either. Change `_dept_out` in `backend/ai_gateway/service.py` if the team prefers otherwise.
- [ ] Install/import `ai.inference`; construct `AIService.from_env()` once; add env vars above.
- [ ] Evidence resolver: `evidence_id → EvidenceInput` (signed URL or bytes; transcript if available).
- [ ] Fusion SQL using `candidate_query_params()`; pgvector column per `(embedding_model, dimension)`.
- [ ] Triage inputs: `support_count`, `case_age_hours`, `recurrence_count`, `location_tags`, `incident_active`.
- [ ] `ToolExecutor` for the copilot with RBAC + parameterised SQL.
- [ ] Persist `AIAnalysis` from `ai_metadata`; AI-override `AuditEvent` on triage decision.
- [ ] Redis `case.ai_requested` consumer calling the adapter; map exceptions → 4xx; surface `warnings`/`degraded` to clients.

## 11 · Backend AI gateway (implemented — `backend/ai_gateway/`)
Routes `POST /cases/intake/analyze`, `/cases/{id}/fusion/analyze`, `/cases/{id}/triage/analyze`, `/cases/{id}/triage/decision` and `POST /copilot/query` now speak the exact §51A shapes and go through `AIGateway` (the only place the backend meets `ai.inference`). Before this, the routes exposed the adapter's internal schemas: a contract-conformant intake body (`evidence_ids`) was a 422, the copilot took an `actor_context` from the request body (spoofable), fusion/triage required the *client* to send candidates/context, and nothing was persisted or audited.

| Concern | Where |
|---|---|
| §51A request/response models (additive fields marked) | `contracts.py` |
| Storage ports: `CaseRepository`, `EvidenceResolver`, `AIAnalysisStore`, `AuditSink`, `ToolExecutor` | `ports.py` |
| §51A.18 roles (enforced in the gateway so queue workers share it), evidence resolution, candidate bounds from `candidate_query_params()`, triage context, `AIAnalysis` persistence, AI-override audit | `service.py` |
| Demo implementations over the **synthetic demo city** (§58, `ai/evaluation/datasets/demo_city_v1`) + copilot `ToolExecutor` | `memory.py` |
| Singleton + `get_actor` (token → `Actor`) + `configure_gateway(...)` | `deps.py` |

**Roles** (§51A.18, JWT role vocabulary): intake — citizen, field_worker + staff; fusion / triage analyze / triage decision — staff (`operator, department_manager, ward_officer, city_admin, system_admin`); copilot — staff + `overlooker` (aggregates only: `search_cases` refused). `overlooker` is **not in `RoleEnum`** yet — add it (or map it) in `backend/models/user.py`. `operator`/`department_manager` are pinned to their own department; a department-scoped role that cannot be placed in a department is refused (deny by default).
**Audit**: every decision writes `TRIAGE_DECISION_RECORDED`; a decision differing from the stored AI recommendation also writes `AI_RECOMMENDATION_OVERRIDDEN` (before = AI recommendation, after = decision + `overridden_fields`). `EventStreamAuditSink` keeps them in memory and best-effort propagates to the Redis `civic:audit` stream — replace with the `AuditEvent` table writer.
**Errors**: `core/exceptions.py` now emits the §51A.1 envelope (`{error:{code,message,details,request_id}}`) for `CivicConnectException`, framework `HTTPException` and request-validation errors; the legacy `detail` key is kept alongside so existing clients/tests keep working.
**Going to production**: implement the four ports with SQLAlchemy/PostGIS/pgvector/object storage, call `configure_gateway(AIGateway(AIService.from_env(tool_executor=<your executor>), repo, resolver, store, audit))` at startup. `AI_GATEWAY_DEMO_CITY_DIR` overrides the demo-city directory. Tests: `backend/tests/test_ai_gateway.py` (23) are the contract the SQL implementation must keep passing — point `install()` at your ports.
**Demo caveat**: the default gateway's clock is pinned to the demo city's "now" (2026-10-01) so case ages are meaningful; it is a demo wiring, not a production default.

**Demo environment (no provider key needed)** — to see the non-degraded local paths, set `AI_FUSION_WEIGHTS_PATH=ai/artifacts/fusion_calibrator/0.1.0+addecff1/fusion_weights.json` (calibrated on *synthetic* pairs; otherwise fusion reports `FUSION_UNCALIBRATED_PRIOR`) and rebuild the B0 classifier locally (`python -m ai.training.src.build_dataset && python -m ai.training.src.train_text_classifier`, weights are gitignored) then `AI_LOCAL_CLASSIFIER_PATH=ai/artifacts/civic_text_b0/<version>`. With nothing set, intake answers `other / confidence 0 / NO_AI_AVAILABLE` (manual categorisation), triage runs rules-only, copilot reports unavailable — all visible in `warnings`.

## 12 · AI-4 resolution review (gateway hook, no §51A endpoint)
`AIGateway.review_resolution(case_id, ResolutionReviewIn(notes, resolution_evidence_ids, citizen_verification, citizen_comment), actor)` → `ResolutionReviewOut` (flags only; `autonomous_closure_allowed` is constant `False`). **Parth wires it into two handlers:** `POST /work-orders/{id}/complete` (§51A.9, pass `notes` + `resolution_evidence_ids`; the assignee check is the route's job) and `POST /cases/{id}/verification` (§51A.10, pass the citizen's `result` as `citizen_verification`; run it as `SYSTEM_ACTOR` and **never return the flags to the citizen**). Surface `unresolved_condition_suspected` / `recommend_verification_request` to the operator and use `recommend_verification_request` to enqueue the citizen verification notification; the case state transition remains the server's decision. The record is stored as `AIAnalysis(task_type="resolution")` without the note text. Original evidence comes from `CaseSnapshot.evidence_ids` through the `EvidenceResolver`.
**What is and is not known** (synthetic, `ai/evaluation/reports/resolution_baseline.md`): the deterministic baseline flags 100% of citizen-reported failures, 0% false flags, requests verification for every unconfirmed case (44% of truly-fixed cases — workload, by design), and never reads note text or photos, so unresolved cases visible only in notes (27% of planted unresolved) or only in photos (24%) are caught solely through the citizen-verification step. The multimodal provider comparison is **not evaluated**: no before/after images exist. Reading the notes text deterministically would need a change in the (frozen) `ai/inference/resolution` baseline — flagged to Tanuj as a decision, not done.

## 13 · AI-5 analytics explanation (gateway + additive endpoint)
`AIGateway.explain_analytics(AnalyticsExplainRequest(scope{ward_id, department_id}), actor)` → `AnalyticsExplainResponse{summary, highlights, citations, facts, grounded, warnings, ai_metadata, analysis_id}`, exposed as **`POST /api/v1/analytics/explain`** — an *additive* endpoint (not in §51A; remove or rename if the team prefers to embed `ai_summary` in the analytics responses). Roles: staff + `overlooker` (aggregates only); department-scoped roles are pinned to their department, out-of-scope requests are 403.
**The numbers are never the model's.** Facts are deterministic and display-ready; `ai.explain_analytics` accepts model prose only if every number and every cited fact id appears in the facts, otherwise a template built from the facts is returned (`EXPLANATION_UNGROUNDED_FALLBACK`). Facts are ordered by urgency (active incidents, hotspots, unusual growth, SLA, recurrence, concentration, totals) because the template fallback quotes only the first ones.
**Parth must implement `AnalyticsFactSource`** (`ports.py`) with SQL that produces the same facts as the executable spec `ai/evaluation/analytics_facts.py` (+ `analytics_reference.py`: `hotspots`, `recurring_sites`, `subcategory_growth` — relative to the city-wide trend —, `sla_risk`, `geographic_concentration`). Parameters (14-day recent window, 90-day baseline, 350 m cells, 150 m / 240-day recurrence) are the spec; change them in one place.
**Contract mismatch found (not mine to change):** `backend/api/v1/analytics.py` exposes mock `/analytics/summary`, `/departments`, `/hotspots`, whereas §51A.13 names `GET /analytics/overview`, `/analytics/departments/{id}` and `/analytics/incidents`.
**Evidence (synthetic):** `ai/evaluation/reports/analytics_ai5.md` — facts recover 3/3 planted hotspots, all 3 planted growth subcategories (plus one subcategory that is genuinely raised by a planted incident, reported separately; no unexplained extras), 3/3 active incidents; guard rails reject 100% of invented numbers/ids across 7 scopes. The recovery partly re-uses the logic that was validated against the same planted truth, so it demonstrates internal consistency, not discovery on unseen data. Scripted providers are test doubles: how well a real LLM words the facts is **not evaluated**.

## 14 · Local image model (road-damage detector) in the intake gateway
`AI_VISION_ONNX_PATH` = the `best.onnx` (or its folder) from notebook 06's bundle (`road_damage/best.onnx` + `model_card.json`); needs `onnxruntime` + `Pillow` in the backend (listed as optional in `backend/requirements.txt`). Unset/missing => the gateway runs exactly as before. With it, `POST /cases/intake/analyze` returns an **additive** `image_analysis` list (per image: detections with class code D00/D10/D20/D40, label, confidence, box in original pixels, civic category/subcategory). Merge policy: a confident answer from another AI is never overridden (a strong disagreement adds `VISION_DISAGREES`); if nothing else answered with confidence (no provider, or `other`/low confidence) the strongest detection becomes the proposal (`roads` / `pothole` for D40, category-only for cracks, confidence capped at 0.8, warning `LOCAL_VISION_USED`) and `requires_confirmation` stays true. A failing model adds `IMAGE_MODEL_FAILED` and never fails the intake. Only evidence that carries bytes is analysed (a signed URL is never fetched here). The numpy decoder was checked against Ultralytics' own predictor on an exported ONNX (top-1 box/class/score parity on every non-empty image of the CI run).
Licences travel with the weights: RDD2020 is non-commercial, RDD2022 is applied as CC BY-SA 4.0, BharatPotHole is unverified (`USE_BHARATPOTHOLE = False` in the notebook keeps it out), Ultralytics is AGPL-3.0.

## 15 · Free AI backends (no OpenAI needed)
`backend/ai_gateway/providers/` implements the frozen `AIProvider` protocol for any OpenAI-compatible endpoint (Gemini, Groq, OpenRouter, Cloudflare Workers AI, OpenAI) with per-task routing (`CompositeProvider`) and env wiring (`build_provider_from_env`, used by `deps.build_ai_service`; it takes precedence over `AIService.from_env`'s OpenAI Responses provider). Nothing under `ai/inference/` changed. Configuration and the full free-stack audit of the design (storage, DB, Redis, hosting, maps, OTP, speech, translation, notifications): `docs/FREE_STACK_PROPOSAL.md`. Verified on mock transports only; run one live call per backend before relying on it. Free tiers can use prompts for product improvement: demo data only.

## 16 · Local text models (M6 classifier, M7 embedder) and browser speech (M8)
- `backend/ai_gateway/text_model.py`: `OnnxTextClassifier` (drop-in for `LocalTextClassifier`; `AI_TEXT_ONNX_PATH`) and `OnnxEmbedder` (cross-language duplicate fusion; `AI_EMBED_ONNX_PATH`). Artifacts are `civic-onnx-text/1` folders with checksummed files; a tampered or wrong-kind folder is refused and the gateway starts without it (warning logged). Embedding fusion reports `FUSION_UNCALIBRATED_PRIOR` until `train_fusion_calibrator --semantic-mode local` has produced weights (`AI_FUSION_EMBEDDING_WEIGHTS_PATH`).
- Training data are LLM-written synthetic complaints (pipeline in `ai/training/src/text_corpus`, notebook 07). Evaluate with `python -m ai.evaluation.run_eval --task intake --system local --artifact <B0 or M6 folder>`.
- Order of operations for the owner: `docs/RUNBOOK_ML.md`.
- **M8 (frontend, Krrish/Vedant — not implemented here):** dictate with the browser Web Speech API and send the *text* to `POST /cases/intake/analyze`; fall back to recording with `MediaRecorder` and uploading the clip as AUDIO evidence (server transcribes with Groq Whisper).
```ts
const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
export function dictate(lang: "hi-IN" | "mr-IN" | "en-IN", onText: (t: string) => void) {
  if (!SR) return null;                       // unsupported (e.g. Firefox): use the MediaRecorder upload fallback
  const r = new SR(); r.lang = lang; r.interimResults = true; r.continuous = false;
  r.onresult = (e: any) => onText(Array.from(e.results).map((x: any) => x[0].transcript).join(" "));
  r.start(); return r;                        // r.stop() when the user taps the mic again
}
```
Chrome/Edge only, needs HTTPS (or localhost) and a mic permission; recognition itself is done by the browser vendor's service, so show the transcript to the citizen for editing before submitting.
