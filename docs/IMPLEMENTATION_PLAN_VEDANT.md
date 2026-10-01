# CivicConnect v2 — Vedant Implementation Plan

**Primary tool:** Antigravity IDE only
**Primary ownership:** Admin + Overlooker frontend, animation/visual polish pass
**Reference:** `/docs/CivicConnect_v2_V1_System_Design.md`

## 1. Mission

Turn the existing Admin and Overlooker prototypes into the V1 operational and city-intelligence interfaces, first achieving correct element placement/layout and only then applying the visual polish pass on Oct 3–4.

## 2. Scope

Admin:
- A01 Admin Login
- A02 Operations Dashboard
- A03 Case Management Workbench
- A04 Case Detail/Evidence
- A05 AI Triage Panel
- A06 Department Coordination
- A07 Department Performance
- A08 City Map
- A09 Ward Heatmap
- A10 Analytics
- A11 Special Boards / Incident Mode
- A12 User Management
- A13 System Settings

Overlooker:
- O01 City Intelligence Home
- O02 City Issues
- O03 Analytics
- O04 Community Intelligence
- O05 City Situation Analysis
- O06 Profile/Access

## 3. Layout phase — through Oct 2 night

Prioritize:
- information hierarchy;
- queue/table density;
- filters;
- map + side-panel relationships;
- KPI cards;
- evidence presentation;
- triage explanations;
- department workload views;
- heatmaps/analytics charts;
- incident boards;
- city-intelligence narrative panels;
- responsive behaviour appropriate to the intended desktop/tablet use.

Do not spend significant time on cinematic effects before the layout is functionally complete.

## 4. Visual polish phase — Oct 3–4

After the layout phase is stable:
- add purposeful transitions;
- animate panel changes and status updates;
- add restrained micro-interactions;
- enhance map/analytics transitions where it improves comprehension;
- ensure effects do not damage performance, readability, or accessibility;
- respect reduced-motion settings.

Animation must communicate state, hierarchy, or interaction. Avoid decorative animation that distracts from municipal operations.

## 5. Integration boundary

Use the Section 51A APIs for:
- case queues;
- case detail;
- AI triage;
- work-order/department data;
- maps/hotspots/recurring problems;
- analytics;
- incidents;
- grounded copilot.

Do not make frontend-only versions of backend facts.

## 6. Repository ownership

Primary:

```text
apps/admin/
apps/overlooker/
```

Shared animation/UI additions:

```text
packages/ui/
```

Coordinate changes to `packages/ui` with Krrish because he owns the base primitives.

## 7. Acceptance criteria by Oct 2 night

- A01–A13 exist and are coherently navigable.
- O01–O06 exist and are coherently navigable.
- Tables, cards, maps, charts, evidence panels and filters are placed according to the V1 design.
- Loading/empty/error states exist.
- AI recommendations are visually distinguished from human decisions.
- Incident mode has a clear case grouping/timeline representation.
- City intelligence separates factual analytics from explanatory narrative.
- No major existing useful prototype functionality is accidentally deleted.

## 8. Antigravity prompt — kickoff/layout

```text
You are implementing the Admin and Overlooker frontend for CivicConnect v2.

READ-ONLY SOURCE OF TRUTH:
- /docs/CivicConnect_v2_V1_System_Design.md
- /docs/IMPLEMENTATION_PLAN_VEDANT.md

Do not modify either document.

First inspect the existing Admin_new/ and Overlooker/ code carefully. Preserve useful product/UI work. Then organize into:
- /apps/admin
- /apps/overlooker
- /packages/ui only for genuinely reusable primitives

Implement all pages specified by A01–A13 and O01–O06.

Through Oct 2 night, prioritize:
- exact information hierarchy,
- page structure,
- navigation,
- tables/queues,
- maps,
- analytics,
- evidence panels,
- AI triage panel,
- department coordination,
- incident board,
- loading/error/empty states.

Do NOT spend significant time on fancy animations or effects yet.

Do not invent API endpoints. Use Section 51A from the system design and isolate data access behind hooks/API client boundaries.

Run build/type checks. Report changed files, completed screens, remaining placeholders, and backend endpoints required by each screen.
```

## 9. Antigravity prompt — animation/polish Oct 3–4

```text
Continue CivicConnect v2 Admin + Overlooker implementation.

Read-only references:
- /docs/CivicConnect_v2_V1_System_Design.md
- /docs/IMPLEMENTATION_PLAN_VEDANT.md
- /docs/TEAM_INTEGRATION_RULES.md

The structural layout is now considered complete. Perform the visual polish pass.

Add restrained, high-quality animations and effects that improve:
- dashboard state transitions,
- case status changes,
- panel/modal transitions,
- map/heatmap interactions,
- analytics reveal/transition,
- incident timeline emphasis,
- AI insight presentation.

Rules:
- preserve readability and performance;
- support reduced motion;
- do not rebuild the layouts;
- do not introduce large dependency changes without necessity;
- no decorative effect should obscure operational data;
- coordinate reusable animation primitives through /packages/ui with Krrish.

Then run build/type/e2e smoke checks and fix integration regressions needed for the Oct 4 demo.
```
