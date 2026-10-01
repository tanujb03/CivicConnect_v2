# CivicConnect v2 — Tanuj Implementation Plan

**Primary tools:** Claude Code + Antigravity IDE
**Primary ownership:** AI/model work, AI inference adapters, AI/backend integration, final end-to-end integration with Parth
**Reference:** `/docs/CivicConnect_v2_V1_System_Design.md`

## 1. Mission

Turn the frozen AI architecture into usable, demonstrable services and then integrate those services with Parth's backend and the frontend surfaces.

Your work is not “build an AI demo beside the application”. It must plug into the Civic Case Engine and the Section 51A API contracts.

## 2. Scope

### Phase A — AI/model work (start 2 Oct)

Read Sections 11–14, 34, 37–40, 51A.5, 51A.7, 51A.8, 51A.15, 57–59.

Deliver:
- reproducible Kaggle training/experimentation assets under `ai/training/`;
- evaluation scripts/reports under `ai/evaluation/`;
- inference-ready artifacts or model adapters under `ai/inference/`;
- clear model/version/config metadata;
- no secrets committed;
- a small local test fixture for inference.

The exact model architecture/dataset is selected from the team's actual available data and kickoff constraints; do not invent unsupported claims. Prioritize a working demonstrator that matches the frozen capability contracts.

### Phase B — AI service adapters

Implement adapters for the required V1 capabilities, with the following priority:

1. AI-1 Multimodal Civic Intake.
2. AI-2 Case Fusion / duplicate analysis.
3. AI-3 Triage recommendation.
4. AI-4 Resolution intelligence.
5. AI-5 Analytics explanation layer.
6. AI-6 Grounded Admin Copilot.

Use an `AIProvider` abstraction and keep provider/model details out of frontend code.

### Phase C — Backend integration (with Parth, 3–4 Oct)

Integrate against:
- `POST /api/v1/cases/intake/analyze`
- `POST /api/v1/cases/{case_id}/fusion/analyze`
- `POST /api/v1/cases/{case_id}/triage/analyze`
- `POST /api/v1/cases/{case_id}/triage/decision`
- `POST /api/v1/copilot/query`
- resolution intelligence hooks in the backend workflow

Do not bypass the API layer from frontend apps.

### Phase D — End-to-end integration

Help Parth validate the full demo path:

```text
citizen input
→ evidence
→ AI intake
→ case
→ fusion
→ triage
→ work order
→ resolution evidence
→ verification
→ analytics
```

## 3. AI implementation rules

- Structured outputs for structured civic fields.
- Preserve source evidence references.
- Return confidence/quality signals where appropriate.
- Log model/version/prompt/schema metadata.
- AI recommendations are not silent workflow decisions.
- The copilot must query authorized CivicConnect tools/data before answering.
- Analytics facts come from deterministic backend aggregation; AI explains them.
- Never expose arbitrary DB credentials to a model.

## 4. Repository ownership

Primary:

```text
ai/
```

Co-owned during integration:

```text
backend/app/ai/
backend/app/cases/       # only where AI hooks are required
packages/shared-types/   # only if contract changes are needed
```

Avoid modifying:

```text
apps/citizen/
apps/admin/
apps/field-worker/
apps/overlooker/
```

unless integration specifically requires a small coordinated change.

## 5. Acceptance criteria

By the end of AI/model phase:
- at least one real inference path runs reproducibly;
- inputs/outputs are documented;
- evaluation metrics/limitations are recorded;
- backend can call the inference adapter without importing notebook code;
- a failure/fallback path exists.

By Oct 4 integration:
- AI-1 returns a structured proposal;
- AI-2 returns duplicate candidates with component signals;
- AI-3 returns triage recommendation + reasons;
- AI-4 can flag inconsistent/unresolved resolution evidence;
- AI-6 answers grounded questions using actual authorized data;
- failures degrade gracefully and are visible in logs/UI.

## 6. Claude Code prompt — kickoff

```text
You are implementing the AI work for CivicConnect v2.

READ-ONLY SOURCE OF TRUTH:
- /docs/CivicConnect_v2_V1_System_Design.md
- /docs/IMPLEMENTATION_PLAN_TANUJ.md

Do not modify either document.
Do not invent a parallel architecture.

First inspect the repository thoroughly. Identify:
1. current frontend/backend structure,
2. existing AI/model code,
3. available datasets/assets,
4. existing environment variables/configuration,
5. current database/API contracts if any.

Then implement only my assigned AI scope. Start with a concrete plan and file map, then execute it.

Requirements:
- Keep all AI training/evaluation/inference work under /ai.
- Separate training/notebook code from production inference adapters.
- Follow Sections 11–14, 37–40, 51A, and 57 of the system design.
- Use structured schemas for civic intake.
- Preserve source evidence references.
- Expose confidence/quality signals where appropriate.
- Do not silently make consequential workflow decisions.
- Do not hard-code secrets.
- Create small deterministic test fixtures.
- Make the inference layer callable from the FastAPI backend later.

At the end:
- run the available tests/checks,
- list changed files,
- explain how the model/inference interface will be consumed by /backend,
- identify any dependency Parth must implement.
```

## 7. Antigravity prompt — integration

```text
You are integrating CivicConnect v2 AI capabilities into the existing implementation.

Read, in read-only mode:
- /docs/CivicConnect_v2_V1_System_Design.md
- /docs/IMPLEMENTATION_PLAN_TANUJ.md
- /docs/IMPLEMENTATION_PLAN_PARTH.md

Inspect the current backend before editing.

Implement the smallest clean integration layer that connects:
- AI-1 intake,
- AI-2 fusion,
- AI-3 triage,
- AI-4 resolution intelligence,
- AI-6 grounded copilot

to the V1 backend contracts.

Respect /api/v1 and Section 51A. Do not let frontend code call the model provider directly.
Use the existing AIProvider abstraction. Keep provider-specific code behind it.

Do not change unrelated frontend or backend modules.
Test the endpoints with representative fixtures.
Verify that errors, low-confidence outputs, and unavailable-model conditions have explicit fallback behaviour.

Finish by reporting:
- files changed,
- endpoints wired,
- test commands/results,
- anything still needed from Parth or frontend owners.
```
