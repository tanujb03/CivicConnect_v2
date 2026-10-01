# CivicConnect v2 — Team Docs

This directory contains the implementation documentation for the frozen CivicConnect v2 V1 build.

## Files

| File | Purpose |
|---|---|
| `CivicConnect_v2_V1_System_Design.md` | Frozen V1 source of truth: product, UX, architecture, domain model, security, API contracts, testing, deployment |
| `COMMON_DIRECTORY_STRUCTURE.md` | Exact monorepo directory structure and ownership |
| `TEAM_INTEGRATION_RULES.md` | Shared timeline, dependency order, merge/integration rules |
| `IMPLEMENTATION_PLAN_TANUJ.md` | AI/model + integration plan |
| `IMPLEMENTATION_PLAN_PARTH.md` | Backend/API/database plan |
| `IMPLEMENTATION_PLAN_KRRISH.md` | Citizen PWA + Field Worker frontend plan |
| `IMPLEMENTATION_PLAN_VEDANT.md` | Admin + Overlooker frontend + animation plan |

## Non-negotiable rule

All four members work from the same frozen system design. AI tools must read the system design and the assigned implementation plan in **read-only mode** before editing code.

The API contracts are defined in **Section 51A** of the system design.

## Execution rule

Do not expand V1 scope during the Oct 1–7 delivery window unless the team explicitly agrees that a change is necessary for a working submission.
