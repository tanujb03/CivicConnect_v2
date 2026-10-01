# CivicConnect v2 — Krrish Implementation Plan

**Primary tool:** Antigravity IDE only
**Primary ownership:** Citizen PWA + Field Worker frontend, shared base UI/layout primitives
**Reference:** `/docs/CivicConnect_v2_V1_System_Design.md`

## 1. Mission

Convert the existing citizen prototype into the V1 **mobile-first PWA experience**, while also laying out the Field Worker app. Focus first on structure, spacing, navigation, information hierarchy, responsiveness, and functional placeholders — not visual effects.

## 2. Scope

### Primary surfaces

Citizen:
- C01 Welcome
- C02 Authentication
- C03 Onboarding
- C04 Dashboard
- C05 Report Issue
- C06 AI Intake Review
- C07 My Civic Cases
- C08 Civic Case Detail
- C09 Notifications
- C10 Community
- C11 City Map
- C12 Expanded Map
- C13 Profile
- C14 Accessibility/Language

Field Worker:
- F01 Assigned Work
- F02 Work Order Detail
- F03 Start Work
- F04 Resolution Evidence
- F05 Complete Work

### Layout phase priorities through Oct 2 night

Implement the V1 page hierarchy and element placement:
- mobile-first viewport;
- bottom navigation where specified;
- touch targets;
- capture controls for camera/audio/location;
- offline status/outbox UI;
- evidence cards;
- case timeline;
- maps;
- accessible states;
- empty/loading/error states.

Do not spend the Oct 2 deadline on elaborate animations.

## 3. Mobile-first requirement

The citizen app is not merely a desktop web page squeezed onto a phone.

Design from the smallest supported phone viewport upward.

Must support:
- camera/photo capture;
- microphone/voice capture;
- GPS;
- offline queue visibility;
- low-bandwidth states;
- large touch targets;
- accessibility preferences;
- installable PWA behaviour where supported.

Desktop/tablet are adaptations, not the primary layout reference.

## 4. Backend integration boundary

Until backend contracts are ready, isolate API calls behind the shared API client/hooks.

Do not invent request formats.

Use the Section 51A contracts for:
- cases;
- intake;
- evidence;
- notifications;
- maps;
- verification;
- sync.

## 5. Repository ownership

Primary:

```text
apps/citizen/
apps/field-worker/
packages/ui/         # base layout/primitives
```

Coordinate with Parth before adding generated API client logic.

## 6. Acceptance criteria by Oct 2 night

Citizen:
- all C01–C14 surfaces exist;
- route/navigation flow works;
- core visual hierarchy matches system design;
- mobile layouts work on common phone widths;
- report flow includes multimodal capture placeholders/hooks;
- offline state/outbox surfaces are visible;
- loading/error/empty states exist;
- no major existing useful feature is lost during migration.

Field Worker:
- F01–F05 surfaces exist;
- work order details and evidence placement are clear;
- start/complete workflow can be wired to API later.

## 7. Antigravity prompt — kickoff

```text
You are implementing the Citizen and Field Worker frontend for CivicConnect v2.

READ-ONLY SOURCE OF TRUTH:
- /docs/CivicConnect_v2_V1_System_Design.md
- /docs/IMPLEMENTATION_PLAN_KRRISH.md

Do not modify either document.

First inspect the existing citizen/ and other prototype frontend code. Preserve useful existing UI/workflows. Then migrate/organize into:
- /apps/citizen
- /apps/field-worker
- /packages/ui where shared primitives are genuinely reusable

Build the V1 layouts specified by C01–C14 and F01–F05.

Critical product rules:
- citizen is a mobile-first PWA;
- multimodal input is core: text, image, audio/voice, video where specified, location;
- offline-first is real UX, not a decorative badge;
- low-bandwidth states must be represented;
- accessibility/language surfaces must be present;
- follow the existing visual identity where useful, but prioritize clarity and functionality;
- do not create backend mocks scattered across components;
- isolate data access through hooks/API-client boundaries.

Until Oct 2 night, do NOT spend significant time on animations, particles, flashy transitions, or decorative effects.
Focus on accurate placement, responsive layout, navigation, states, and functional wiring points.

Run the frontend build/type checks and fix major layout/build errors.
At the end report:
- files changed,
- pages completed,
- remaining placeholders,
- API contracts each page will consume.
```

## 8. Antigravity prompt — Oct 3 integration pass

```text
Continue CivicConnect v2 Citizen + Field Worker implementation.

Read-only references:
- /docs/CivicConnect_v2_V1_System_Design.md
- /docs/IMPLEMENTATION_PLAN_KRRISH.md
- /docs/TEAM_INTEGRATION_RULES.md

Now wire the already-built layouts to the generated/shared API client and real backend contracts.

Prioritize:
1. auth,
2. report issue + evidence upload-init,
3. AI intake review,
4. case creation,
5. my cases/detail/timeline,
6. notifications,
7. verification/reopen,
8. field worker work orders,
9. resolution evidence,
10. offline mutation queue/sync.

Do not invent endpoints. Use /api/v1 and Section 51A.
Keep UI components decoupled from raw fetch logic.

Fix only integration regressions required for the end-to-end demo.
```
