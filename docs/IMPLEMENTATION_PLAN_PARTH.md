# CivicConnect v2 — Parth Implementation Plan

**Primary tool:** Antigravity IDE only
**Primary ownership:** Backend, PostgreSQL/PostGIS, Redis/event flow, API/OpenAPI, authentication/RBAC, core workflow
**Reference:** `/docs/CivicConnect_v2_V1_System_Design.md`

## 1. Mission

Build the production-like FastAPI backend and system of record that every frontend and AI component uses.

The backend must be contract-first and match Section 51A exactly enough for generated client use.

## 2. Scope

### Phase A — backend foundation (start immediately)

Read Sections 18–25, 27–35, 41–48, 51–56.

Implement:
- FastAPI application shell;
- configuration/environment management;
- PostgreSQL connection and SQLAlchemy models;
- Alembic migrations;
- PostGIS support;
- authentication/session foundation;
- RBAC/access scopes;
- standard error envelope;
- request IDs and structured logging;
- health/readiness endpoints;
- OpenAPI generation.

### Phase B — Core Civic Case workflow

Implement:
- User
- Ward
- Department
- CivicCase
- ReportSignal
- EvidenceItem
- AIAnalysis
- CaseRelation
- Support
- WorkOrder
- Verification
- Notification
- Incident
- AuditEvent

Then implement the case state machine from Section 35.

### Phase C — API surface

Prioritize these endpoints:
- `/auth/*`
- `/me/*`
- `/cases`
- `/evidence/*`
- `/work-orders/*`
- `/cases/{case_id}/verification`
- `/cases/{case_id}/timeline`
- `/map/*`
- `/analytics/*`
- `/incidents/*`
- `/sync/*`
- `/health/*`

Wire AI endpoints with clean adapter interfaces when Tanuj is ready; do not block the rest of the backend on the model implementation.

### Phase D — Redis/events

Implement the minimal event architecture required for:
- notifications,
- async AI jobs,
- background sync/processing,
- audit/event propagation where appropriate.

Redis Streams is the event/job mechanism from the frozen architecture.

## 3. API rules

Follow Section 51A:
- `/api/v1` base path;
- bearer auth;
- `Idempotency-Key` for retryable mutations;
- stable error codes;
- cursor pagination;
- `X-Request-ID` correlation;
- no direct media bytes in PostgreSQL;
- OpenAPI is the shared contract.

The server is authoritative for:
- case IDs,
- state,
- timestamps,
- priority,
- assignment,
- permissions.

## 4. Repository ownership

Primary:

```text
backend/
infra/
```

Shared/generated:

```text
packages/api-client/
packages/shared-types/
```

Do not redesign frontend layouts.

## 5. Acceptance criteria

By Oct 2 night:
- backend boots reliably;
- migrations run;
- DB schema exists;
- auth works for at least the required demo roles;
- core case CRUD works;
- evidence metadata/upload-init flow works;
- OpenAPI is generated;
- basic API tests exist;
- health endpoints work;
- frontend owners can point at a stable API contract or mock adapter.

By Oct 4:
- AI hooks are integrated;
- work orders function;
- verification/reopen flow works;
- analytics/map endpoints return real DB-backed data;
- offline sync mutation endpoint works idempotently;
- audit events are visible;
- core demo path is end-to-end.

## 6. Antigravity prompt — kickoff

```text
You are implementing the backend for CivicConnect v2.

READ-ONLY SOURCE OF TRUTH:
- /docs/CivicConnect_v2_V1_System_Design.md
- /docs/IMPLEMENTATION_PLAN_PARTH.md

Do not modify either document.
Do not invent a parallel backend architecture.

First inspect the existing repository and identify what can be preserved from the SIH prototype. Then create the agreed monorepo backend structure without deleting useful frontend work.

Implement the FastAPI modular monolith defined by the system design.
Priorities:
1. project/configuration shell,
2. PostgreSQL + PostGIS + SQLAlchemy + Alembic,
3. auth/RBAC,
4. core entities and state machine,
5. Section 51A API contracts,
6. OpenAPI,
7. evidence/media metadata workflow,
8. work orders + verification,
9. Redis/event foundations,
10. audit/logging/health.

Rules:
- /api/v1
- stable error envelope with error.code
- Idempotency-Key for mutation endpoints
- cursor pagination
- server-authoritative workflow state
- role-scoped authorization
- no secrets committed
- no AI provider calls directly from route handlers when an adapter/service layer is appropriate
- no duplicated frontend API types; expose OpenAPI for generation

Build in small verified steps. Run migrations, type/static checks where applicable, API tests, and smoke tests after each major subsystem.

At the end report changed files, endpoints completed, migration status, test commands/results, and any integration dependency for Tanuj.
```

## 7. Antigravity prompt — integration with Tanuj

```text
Continue CivicConnect v2 backend implementation.

Read-only references:
- /docs/CivicConnect_v2_V1_System_Design.md
- /docs/IMPLEMENTATION_PLAN_PARTH.md
- /docs/IMPLEMENTATION_PLAN_TANUJ.md

Now integrate the AI adapter layer into the already-working backend without changing the public API contract.

Wire:
- POST /api/v1/cases/intake/analyze
- POST /api/v1/cases/{case_id}/fusion/analyze
- POST /api/v1/cases/{case_id}/triage/analyze
- POST /api/v1/cases/{case_id}/triage/decision
- POST /api/v1/copilot/query
- resolution intelligence into the appropriate case/work-order flow

Keep the model provider behind AIProvider/service interfaces.
Validate role permissions, input schemas, logging, AI metadata, and graceful failure.

Then verify the entire demo workflow using seeded/test data.
Do not modify unrelated frontend code.
```
