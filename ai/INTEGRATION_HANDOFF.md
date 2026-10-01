# AI → Backend hand-off (for Parth)

Status: **Phase A complete (AI/model work + production adapter). Backend wiring not started.** Everything below is the contract between `ai/inference` and `backend/app/ai`. It implements the frozen design (§11–14, §37–40, §51A.5/7/8/15) and does not change any API.

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
| `AI_FUSION_WEIGHTS_PATH`, `AI_FUSION_EMBEDDING_WEIGHTS_PATH` | calibrated weights for the lexical / embedding semantic signal |

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
- [ ] Decide department value in API responses: canonical ID (`water_supply`, what the AI emits) vs the 51A.8 literal (`WATER`).
- [ ] Install/import `ai.inference`; construct `AIService.from_env()` once; add env vars above.
- [ ] Evidence resolver: `evidence_id → EvidenceInput` (signed URL or bytes; transcript if available).
- [ ] Fusion SQL using `candidate_query_params()`; pgvector column per `(embedding_model, dimension)`.
- [ ] Triage inputs: `support_count`, `case_age_hours`, `recurrence_count`, `location_tags`, `incident_active`.
- [ ] `ToolExecutor` for the copilot with RBAC + parameterised SQL.
- [ ] Persist `AIAnalysis` from `ai_metadata`; AI-override `AuditEvent` on triage decision.
- [ ] Redis `case.ai_requested` consumer calling the adapter; map exceptions → 4xx; surface `warnings`/`degraded` to clients.
