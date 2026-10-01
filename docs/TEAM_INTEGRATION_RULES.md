# CivicConnect v2 — Team Integration Rules

**Execution window:** 1–7 October 2026
**V1 source of truth:** `/docs/CivicConnect_v2_V1_System_Design.md`

## 1. Team execution plan

### 1–2 October
- Parth: backend implementation starts.
- Krrish: Citizen PWA + Field Worker layout/element placement.
- Vedant: Admin + Overlooker layout/element placement.
- No animation/effect rabbit holes during layout phase.
- Tanuj: starts AI/model work on Kaggle on 2 October; after the training milestone, prepares AI inference/integration artifacts.

### 3–4 October
- Vedant: animation/visual-effect pass on his assigned applications; contribute animation primitives to shared UI where practical.
- Tanuj + Parth: frontend/backend integration, AI integration, data flow, auth, persistence, media, and end-to-end case lifecycle.
- Krrish: fixes layout/integration regressions in Citizen/Field Worker as requested.

### 5 October
- Final finishing touches and prototype stabilization.
- PPT creation using the SIH 2026 PPT structure with CivicConnect v2 content.

### 6 October
- Innovibe submission.

### 6–7 October
- Hacksphere finishing work and submission using the same prototype/PPT baseline.

## 2. Integration order

The integration path should follow:

```text
Database/schema
    ↓
Backend API + OpenAPI
    ↓
Generated API client/types
    ↓
Frontend data hooks
    ↓
Frontend screens
    ↓
AI services/adapters
    ↓
End-to-end case flow
    ↓
Offline + media + verification testing
```

The team can develop in parallel, but final integration follows this dependency direction.

## 3. Shared contract rules

- The backend is authoritative for case IDs, status, assignment, priority, timestamps, and workflow state.
- Clients generate idempotency keys for retryable mutations.
- Media uploads use the evidence upload contract; do not upload raw files directly through arbitrary case endpoints.
- API responses are consumed through the generated/shared client.
- AI endpoints return proposals/recommendations; authorized workflow actions remain explicit.
- No frontend screen should invent backend fields that are absent from the contract.

## 4. What “done” means by Oct 2 night for frontend layout

Each assigned surface should have:
- Correct page hierarchy.
- Correct major components from the V1 page specification.
- Responsive/mobile behaviour where applicable.
- Correct navigation shell.
- No major placeholder boxes where actual V1 components are already specified.
- Loading/error/empty state placeholders.
- API hooks or mocked contract adapters clearly isolated where backend is not yet ready.
- No time spent on nonessential animation.

## 5. What “done” means by Oct 4 night for integration

The core demo path should work:

```text
Citizen multimodal report
→ offline/online queue handling
→ AI intake
→ case creation
→ duplicate/case fusion suggestion
→ admin triage
→ department/work order
→ field worker evidence
→ citizen verification
→ analytics/timeline
```

Anything that cannot be fully completed should fail gracefully and visibly rather than silently.

## 6. Conflict rule

If two members need the same file:
1. The primary owner remains responsible for the file.
2. The second member explains the required integration change.
3. Prefer a small, coordinated commit rather than two simultaneous rewrites.
4. Never resolve a merge conflict by deleting another person's work without understanding it.

## 7. AI-tool common instruction

Use this exact rule in every AI prompt:

> Treat `/docs/CivicConnect_v2_V1_System_Design.md` and the contributor's implementation plan as READ-ONLY source-of-truth documents. Do not edit them. Do not contradict them. Do not invent a parallel architecture. Inspect existing code first, preserve useful work, implement only within the assigned scope, and expose clean interfaces for other team members.
