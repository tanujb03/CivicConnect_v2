# CivicConnect v2 — Common Directory Structure

**Status:** Implementation standard for V1
**Source of truth:** `/docs/CivicConnect_v2_V1_System_Design.md`

## 1. Purpose

All four members must work in the same repository structure. The goal is to prevent duplicated implementations, misplaced code, conflicting conventions, and integration surprises during the Oct 1–7 execution window.

The repository is a single monorepo:

```text
civicconnect-v2/
├── apps/
│   ├── citizen/
│   ├── admin/
│   ├── field-worker/
│   └── overlooker/
├── backend/
├── ai/
├── packages/
├── infra/
├── scripts/
├── docs/
├── .env.example
├── .gitignore
└── README.md
```

## 2. What belongs where

### `apps/citizen/`
The citizen-facing **mobile-first PWA**. It must work well on phones first, then adapt to tablet/desktop.

Owns the citizen surfaces C01–C14 from the system design.

### `apps/admin/`
Department/operator/admin application. Owns A01–A13.

### `apps/field-worker/`
The field execution application. Owns F01–F05.

### `apps/overlooker/`
City intelligence / command-center application. Owns O01–O06.

### `backend/`
FastAPI modular monolith, database access, auth/RBAC, Civic Case lifecycle, workflow logic, APIs, events, notifications, geo queries, and AI orchestration.

### `ai/`
AI training, evaluation, inference adapters, prompts/schema configuration, and generated model artifacts. This is where Kaggle work belongs.

### `packages/api-client/`
Generated TypeScript client/types derived from the backend OpenAPI contract. Do not hand-create competing copies of API request/response types in individual apps.

### `packages/shared-types/`
Shared frontend domain types that genuinely need to exist outside the generated API client.

### `packages/schemas/`
Shared validation schemas when cross-app reuse is useful.

### `packages/ui/`
Reusable UI primitives/design tokens. Avoid putting app-specific workflow logic here.

### `packages/config/`
Shared lint/build/test/configuration where useful.

### `infra/`
Docker, local compose files, deployment scripts, and infrastructure configuration.

### `scripts/`
Repo-level one-off or repeatable development/verification scripts.

### `docs/`
All implementation documentation. The four personal plans live here alongside the frozen system design.

## 3. Ownership

| Area | Primary owner | Supporting owner(s) |
|---|---|---|
| `apps/citizen` | Krrish | Tanuj for integration; Vedant for agreed animation primitives after layout freeze |
| `apps/field-worker` | Krrish | Parth/Tanuj for API integration |
| `apps/admin` | Vedant | Tanuj/Parth for integration |
| `apps/overlooker` | Vedant | Tanuj/Parth for integration |
| `packages/ui` base layout primitives | Krrish | Vedant after Oct 2 for animation layer |
| `backend` | Parth | Tanuj from Oct 3 for AI/integration |
| `ai` | Tanuj | Parth for backend adapter wiring |
| `packages/api-client` | Parth | Tanuj during integration |
| `docs` | All read; Tanuj coordinates | All contributors may add factual implementation notes only when needed |

Ownership means “primary implementation owner”, not “other members may never touch the files”. Integration changes should be coordinated with the owner.

## 4. Migration rule from the old CivicConnect repo

The existing prototype currently has:

```text
citizen/
Admin_new/
Overlooker/
```

During migration:

```text
citizen/      → apps/citizen/
Admin_new/    → apps/admin/
Overlooker/   → apps/overlooker/
```

Do not blindly rewrite or delete the old code. First inspect it, preserve useful product/UI work, then migrate/rename in a controlled commit.

## 5. Forbidden structure patterns

Do not create:

```text
frontend-final/
frontend-new/
frontend-new2/
backend-final/
api2/
models-final/
shared-new/
```

Do not duplicate the same API types in multiple apps.

Do not create separate backend implementations for Citizen/Admin/Overlooker.

Do not place secrets or local `.env` files under version control.

## 6. Required AI-tool startup behaviour

Every AI implementation session must:

1. Read `/docs/CivicConnect_v2_V1_System_Design.md` in read-only mode.
2. Read the contributor’s `/docs/IMPLEMENTATION_PLAN_*.md` in read-only mode.
3. Inspect the repository before modifying anything.
4. Confirm the assigned ownership boundary.
5. Reuse existing code where appropriate rather than recreating functionality.
6. Respect the API contract in Section 51A.
7. Run targeted tests/type checks/build checks after meaningful changes.
8. Summarize changed files and any integration dependency at the end.

## 7. Commit guidance

Use focused commits. Examples:

```text
feat(citizen): rebuild report issue flow layout
feat(admin): implement case workbench layout
feat(backend): add civic case persistence API
feat(ai): add civic intake inference adapter
fix(api): enforce idempotent sync mutations
chore(repo): migrate prototype apps into monorepo structure
```

Avoid giant “everything” commits unless necessary for the migration baseline.
