# CivicConnect v2 — System Design Document
## V1 — Product, UX, Architecture & Implementation Specification

**Document status:** V1 — working specification  
**Revision policy:** Up to 3 structured review rounds; after Round 3, freeze V1 and implement against the frozen specification.  
**Prepared:** 1 October 2026  
**Current repository:** `tanujb03/SIH2025_CivicConnect`  
**Original project:** SIH-era CivicConnect prototype  
**Target:** Full-stack, AI-assisted civic issue intelligence and resolution platform

---

# 0. Executive Definition

CivicConnect v2 is a **multimodal, multilingual, offline-capable civic issue intelligence and resolution platform**.

It connects:

- citizens,
- municipal/department operators,
- field workers,
- ward/city administrators,
- city-level oversight,

through a single persistent **Civic Case** lifecycle.

The central product abstraction is **not a complaint/report**.

It is a **Civic Case**.

A citizen report is an input signal. Multiple reports, media items, confirmations, field observations, and administrative actions can converge on the same Civic Case.

The system converts:

> messy citizen observations → structured civic intelligence → municipal workflow → field execution → evidence-backed resolution → citizen verification → city-level learning.

AI is used only where semantic, multimodal, multilingual, or pattern-recognition capability provides a real advantage over deterministic software.

---

# 1. V1 Goals

## 1.1 Primary goal

Build CivicConnect into a genuinely functional full-stack system rather than a frontend prototype.

## 1.2 Product goals

V1 must provide:

1. Real authentication and authorization.
2. Persistent PostgreSQL data.
3. Geospatial civic cases.
4. Citizen issue intake using text, image, audio and location.
5. Offline-first citizen submission queue.
6. Multilingual/voice-first interaction.
7. AI-assisted issue understanding.
8. AI-assisted duplicate/case fusion.
9. AI-assisted triage and routing.
10. Department workflows and work orders.
11. Resolution evidence.
12. Citizen verification/reopening.
13. Community support/evidence.
14. Operational dashboards.
15. City intelligence/analytics.
16. Recurring-problem detection.
17. Incident/special-board workflows.
18. Auditability and role-based access.
19. Secure media handling.
20. A deployment architecture suitable for a serious hackathon demo and continued portfolio development.

## 1.3 Non-goals for V1

The following remain architectural extension points rather than mandatory V1 implementation:

- physical IoT hardware,
- city-wide government system integration,
- autonomous municipal decision-making,
- autonomous emergency dispatch,
- fully native Android/iOS applications,
- predictive maintenance claims requiring large historical datasets,
- facial recognition,
- citizen reputation scoring,
- automatic punitive action against reporters.

---

# 2. Product Thesis

The original CivicConnect asked:

> How can citizens report civic problems?

CivicConnect v2 asks:

> How can a city turn noisy, multilingual, multimodal citizen observations into structured, prioritized, executable and verifiable civic action — and learn from the resulting cases?

This distinction drives the architecture.

---

# 3. Core Domain Model: Civic Case

A Civic Case is the canonical unit of civic work.

Example:

```text
Civic Case #CC-1042
Major pothole near school

Reports/signals:
  Citizen A — photo + GPS
  Citizen B — voice + GPS
  Citizen C — text
  Citizen D — supporting vote

AI:
  Category: Road Damage
  Subcategory: Pothole
  Severity: High
  Suggested department: Road Maintenance
  Duplicate confidence: 0.92

Workflow:
  Assigned
  → Work Order Created
  → Field Work Started
  → Evidence Uploaded
  → Citizen Verification
  → Resolved
```

## 3.1 Civic Case vs Report

A **report** is an observation.

A **Civic Case** is the underlying municipal problem.

Multiple reports can attach to one case.

This enables:

- duplicate reduction,
- collective evidence,
- support counts,
- better prioritization,
- cleaner municipal workload,
- recurring issue analysis.

---

# 4. Core Personas

## 4.1 Citizen

Can:

- report,
- support,
- contribute evidence,
- track cases,
- verify resolutions,
- receive notifications,
- manage language/accessibility preferences.

## 4.2 Department Operator

Can:

- review cases,
- correct AI suggestions,
- assign cases,
- create work orders,
- update status,
- request evidence,
- coordinate work.

## 4.3 Department Manager

Can:

- manage workload,
- monitor SLA compliance,
- assign teams,
- inspect performance,
- review escalations.

## 4.4 Ward Officer

Can:

- see ward-specific cases,
- inspect hotspots,
- manage ward incidents,
- coordinate departments.

## 4.5 City Administrator

Can:

- view city-wide intelligence,
- manage configuration,
- inspect department performance,
- access city analytics.

## 4.6 Field Worker

Can:

- receive work orders,
- navigate to location,
- start work,
- upload before/after evidence,
- mark work completed.

## 4.7 System Administrator

Can:

- manage roles,
- departments,
- categories,
- ward boundaries,
- SLA rules,
- AI thresholds,
- integrations,
- audit/security configuration.

---

# 5. Current Repository Baseline

The existing repository was inspected before defining V1.

Repository:

`tanujb03/SIH2025_CivicConnect`

It currently contains three frontend applications:

```text
SIH2025_CivicConnect/
├── citizen/
├── Admin_new/
└── Overlooker/
```

There is no production backend service in the repository.

The citizen application currently uses React context and mock data. `AppContext.tsx` initializes issues from `mockIssues` and mutations such as ADD_ISSUE, UPDATE_ISSUE and UPVOTE_ISSUE only modify in-memory React state.

The citizen `package.json` already contains:

- React
- Vite
- TypeScript
- Tailwind CSS
- React Router
- Leaflet / react-leaflet
- MapLibre
- Supabase client
- webcam support
- Framer Motion
- Lucide

The presence of `@supabase/supabase-js` is not considered proof of a functioning backend integration; V1 will replace the mock-state architecture with an explicit backend contract.

---

# 6. Existing Citizen Prototype — Page/Surface Inventory

The current citizen prototype contains the following major surfaces/components:

- Welcome
- Login
- Onboarding
- Dashboard
- Report Issue
- My Reports
- Issue Detail
- Notifications
- Community
- City Map
- Expanded Map
- Profile
- Bottom Navigation
- Transition Screen

The V1 design retains the useful product intent but upgrades every surface from mock/prototype behaviour to a real workflow.

---

# 7. Citizen Application — V1 Page-by-Page Specification

## C01 — Welcome

### Purpose

First-touch entry point.

### UI

Top:
- CivicConnect logo
- concise civic mission statement

Center:
- visual representation of citizen → city workflow

Primary CTA:
- `Get Started`

Secondary:
- `I already have an account`

Footer:
- language selector
- accessibility control

### Behaviour

`Get Started` → onboarding/auth flow.

`I already have an account` → login.

Language selection applies immediately.

No civic data is fetched on this page.

---

# C02 — Authentication

### Purpose

Authenticate citizen securely.

### UI

Header:
- CivicConnect

Main:
- phone/email input
- OTP/passwordless option
- authentication status

Secondary:
- language
- help
- accessibility

### Backend

```text
POST /api/v1/auth/request-otp
POST /api/v1/auth/verify-otp
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/me
```

### Security

- short-lived access token
- rotating refresh token
- secure cookie where applicable
- server-side role verification
- rate limiting
- audit events

---

# C03 — Onboarding

### Purpose

Establish citizen context.

### Fields

- display name
- preferred language
- optional home locality
- ward inference from location/address where possible
- notification preferences
- accessibility preferences
- location permission
- microphone/camera permission explanations

### Principle

Do not require unnecessary personal information.

The system should be useful without collecting excessive PII.

---

# C04 — Citizen Dashboard

### Purpose

Answer:

> What needs my attention?

### Top

Greeting + locality.

### Attention section

Examples:

- `Your case needs verification`
- `A nearby case is unresolved`
- `Your report was assigned to Roads`
- `A case you supported was resolved`

### Quick actions

- Report an Issue
- Nearby Issues
- My Cases
- Community

### Intelligence cards

- active cases
- nearby unresolved cases
- cases awaiting citizen action

### Data

All values come from backend APIs.

No hard-coded civic statistics.

---

# C05 — Report Issue

This is the primary citizen AI surface.

## Step 1 — Capture

User can provide:

- text
- image
- multiple images
- short video
- voice recording
- location
- optional landmark

The user may provide any subset.

## Step 2 — Offline handling

If online:

```text
capture → local staging → upload → API
```

If offline:

```text
capture
→ IndexedDB
→ local case draft
→ "Saved offline"
→ background synchronization
```

## Step 3 — AI intake

Backend creates an intake job.

AI produces structured suggestions:

```json
{
  "category": "roads",
  "subcategory": "pothole",
  "severity": "high",
  "summary": "Large pothole near school entrance",
  "suggested_department": "road_maintenance",
  "confidence": 0.94
}
```

## Step 4 — Citizen confirmation

Display:

> We understood your issue as:

**Large pothole — High severity — Road Maintenance**

Actions:

- `Looks correct`
- `Edit`

AI suggestions never silently become immutable truth.

## Step 5 — Duplicate discovery

Show possible related cases:

```text
Possible existing case

CC-1042
92% similar
74m away

[Support existing case]
[Create new case]
```

## Step 6 — Submission

Create a Civic Case or attach evidence to an existing case.

Return:

- case ID
- status
- expected next step
- notification preference

---

# C06 — AI Intake Review

This is a dedicated confirmation state within Report Issue.

### Display

- original media
- extracted text/transcript
- detected language
- category
- subcategory
- severity
- department
- location
- AI confidence
- related cases

### Explainability

For important AI recommendations, show concise evidence:

```text
Why this category?

• Text mentions "pothole"
• Image contains road-surface damage
• Location is on a mapped road
```

---

# C07 — My Civic Cases

Rename the old "My Reports" concept.

Tabs:

- Active
- Awaiting Me
- Resolved
- Reopened
- Supported

Each card:

- case ID
- title
- category
- location
- status
- priority
- last update
- supporting citizen count

Filters:

- category
- status
- date

---

# C08 — Civic Case Detail

This becomes a full case timeline.

### Header

Case ID  
Title  
Current status  
Priority

### Evidence

- original photo/video/audio
- additional citizen evidence

### Timeline

```text
Reported
↓
AI processed
↓
Case created
↓
Department assigned
↓
Work order created
↓
Field work started
↓
Resolution evidence uploaded
↓
Verification requested
↓
Resolved
```

### Community

- number of supporters
- related reports
- additional evidence

### Citizen actions

- support
- add evidence
- verify
- dispute/reopen where eligible

---

# C09 — Notifications

Notifications are workflow events.

Examples:

- Case assigned
- Similar case found
- Department requested information
- Work started
- Resolution submitted
- Verification required
- Case reopened
- Case resolved
- Incident affecting user's locality

Each notification deep-links into the relevant entity.

---

# C10 — Community

Community is not a generic social feed.

It is a **collective civic evidence layer**.

Users can:

- support a Civic Case
- add evidence
- confirm issue still exists
- report outdated/incorrect content
- view nearby civic activity

Do not create citizen leaderboards.

The goal is useful participation, not incentivized spam.

---

# C11 — City Map

MapLibre GL JS.

Modes:

1. Nearby cases
2. Case clusters
3. Hotspots
4. Resolved cases
5. Recurring problems
6. SLA-risk cases
7. Category filters
8. Department filters
9. Ward filters

Map queries use PostGIS.

---

# C12 — Expanded Map

Full-screen map.

Features:

- viewport-based API queries
- clustering
- case detail drawer
- heatmap layer
- hotspot layer
- current location
- filter controls
- offline cached map shell

The frontend must never download the entire city's case set just to render the map.

---

# C13 — Profile

Sections:

### Personal

- name
- contact
- language
- accessibility

### Civic activity

- cases reported
- cases supported
- evidence contributions
- verification contributions

### Settings

- notifications
- language
- dark mode
- location
- privacy

No public reputation score.

---

# C14 — Accessibility / Language Settings

Language applies to:

- UI
- system notifications
- AI summaries
- voice interaction
- case status explanations

Accessibility:

- large text
- high contrast
- reduced motion
- screen reader support
- voice playback
- simplified language mode

---

# 8. Admin Application — V1 Page-by-Page Specification

The current `Admin_new` application already contains:

- Dashboard
- City Map
- Analytics
- Department Coordination
- Department Performance
- Issue Management
- Issue Details
- Special Boards
- System Settings
- User Management
- Ward Heatmap
- Login
- Recent Issues

V1 preserves these concepts but converts them into a coherent municipal operations system.

---

# A01 — Admin Login

Role-aware authentication.

After login:

```text
user → role → permission set → allowed routes
```

No frontend-only role enforcement.

---

# A02 — Operations Dashboard

The first screen answers:

> What needs municipal attention now?

### KPI strip

- Active Cases
- Critical Cases
- SLA Risk
- Unassigned
- Awaiting Verification
- Reopened

### Priority Queue

Sorted by deterministic priority score, with AI recommendation shown separately.

### AI Situation Summary

Example:

> Road-related cases are concentrated in W12 and W18. Three locations have recurring reports.

Every summary must be backed by database records and link to the evidence.

---

# A03 — Case Management Workbench

Central administrative screen.

Capabilities:

- search
- filter
- sort
- inspect
- correct classification
- merge
- split
- assign
- escalate
- create work order
- request information
- change status
- add internal note
- upload evidence

AI suggestions are editable.

---

# A04 — Case Detail / Evidence

Display:

- citizen input
- media
- transcript
- AI classification
- confidence
- related cases
- duplicate reasoning
- priority reasoning
- timeline
- department
- work order
- resolution evidence
- citizen verification

---

# A05 — AI Triage Panel

AI recommendations:

```text
Category
Subcategory
Severity
Priority
Department
SLA class
```

Admin can accept/edit/reject.

All overrides are audited.

---

# A06 — Department Coordination

Convert a Civic Case into a Work Order.

```text
Civic Case
   ↓
Work Order
   ↓
Department
   ↓
Team / Worker
   ↓
Execution
   ↓
Evidence
```

Work Order fields:

- case
- department
- assigned team
- location
- priority
- instructions
- deadline
- required evidence
- status

---

# A07 — Department Performance

Metrics:

- incoming workload
- active workload
- resolved
- median resolution time
- SLA compliance
- reopened
- backlog age
- recurring cases
- workload by severity

Avoid simplistic rankings that ignore workload composition.

---

# A08 — City Map

Operational map.

Layers:

- cases
- clusters
- heatmap
- wards
- departments
- hotspots
- SLA risk
- recurring locations
- active incidents

---

# A09 — Ward Heatmap

Ward-level comparison of:

- case volume
- severity
- category distribution
- resolution time
- backlog
- recurrence

The heatmap is derived from real DB aggregates.

---

# A10 — Analytics

Three levels:

### Descriptive

What happened?

### Diagnostic

Where/why is it concentrated?

### Pattern detection

What is unusual or recurring?

---

# A11 — Special Boards / Incident Mode

Create temporary operational views for events such as:

- flooding
- major road blockage
- infrastructure failure
- storm response
- large public events

Incident board:

```text
Incident
├── Cases
├── Departments
├── Work Orders
├── Timeline
├── Geographic boundary
├── Situation updates
└── Resolution summary
```

---

# A12 — User Management

RBAC.

Roles:

```text
CITIZEN
FIELD_WORKER
DEPARTMENT_OPERATOR
DEPARTMENT_MANAGER
WARD_OFFICER
CITY_ADMIN
SUPER_ADMIN
```

Capabilities are permission-based.

---

# A13 — System Settings

Configurable:

- categories
- subcategories
- departments
- ward boundaries
- SLA rules
- escalation rules
- AI confidence thresholds
- duplicate threshold
- notification policies
- supported languages
- moderation rules

---

# 9. Field Worker Application

The existing prototype does not fully represent this persona.

V1 adds a lightweight field workflow.

## F01 — Assigned Work

List of work orders.

## F02 — Work Order Detail

- location
- issue
- original evidence
- priority
- SLA
- instructions

## F03 — Start Work

Records:

- start time
- worker
- location confirmation

## F04 — Resolution Evidence

Upload:

- after photo
- optional video
- work note
- material/task details

## F05 — Complete Work

Marks work complete.

Does not necessarily close the Civic Case.

The case moves to verification.

---

# 10. Overlooker — City Intelligence / Command Center

The current Overlooker contains:

- Home
- Issues
- Analytics
- Community
- Profile

V1 redefines Overlooker as the city-wide intelligence surface.

---

# O01 — City Intelligence Home

Display:

- active cases
- critical cases
- SLA risk
- emerging hotspots
- recurring problem areas
- department load
- recent incidents

Question answered:

> What is happening across the city?

---

# O02 — City Issues

Cross-city case explorer.

Filters:

- ward
- category
- department
- severity
- priority
- age
- status

---

# O03 — Analytics

City-level:

- trends
- spatial clusters
- recurrence
- workload
- SLA
- resolution
- reopening

---

# O04 — Community Intelligence

Aggregates:

- citizen support
- evidence volume
- active community confirmations
- unresolved community hotspots

This is not a social feed.

---

# O05 — City Situation Analysis

AI-generated, database-grounded summaries.

Example:

```text
Emerging hotspot
Ward 18 — sanitation

Evidence:
• 31 cases in 7 days
• 19 concentrated within 800m
• 2 recurring locations
• 27% above previous 30-day baseline
```

---

# O06 — Profile / Access

Administrative identity and permission context.

---

# 11. AI Architecture

AI is divided into independent capabilities.

## AI-1 Multimodal Civic Intake

Inputs:

- text
- image
- audio transcript
- location/context

Output:

structured issue proposal.

Use structured outputs rather than free-form parsing.

OpenAI's current API supports image inputs and Structured Outputs; Structured Outputs constrain model responses to a supplied JSON schema, which is appropriate for civic intake schemas. citeturn3search3turn3search0

---

## AI-2 Case Fusion Engine

Uses:

1. lexical similarity
2. embeddings
3. geospatial distance
4. category match
5. time window
6. image similarity where useful

Embeddings are suitable for semantic search, clustering and anomaly detection. citeturn3search1

Store embeddings in PostgreSQL using pgvector.

pgvector 0.8.6 is current as of July 29, 2026 and includes PostgreSQL 18 support improvements. citeturn0search4

---

## AI-3 Triage Engine

AI proposes:

- severity
- priority
- department
- SLA class

The final operational state remains governed by deterministic rules and authorized human operators.

---

## AI-4 Resolution Intelligence

Inputs:

- original evidence
- resolution evidence
- field notes
- citizen verification

Output:

- evidence consistency signal
- possible unresolved condition
- recommendation to request verification

Never autonomously close a case solely from model output.

---

## AI-5 Civic Analytics Intelligence

Detect:

- emerging hotspots
- anomalies
- recurrence
- unusual category growth
- geographic concentration
- SLA-risk patterns

Deterministic SQL/statistical aggregation should produce the factual numbers; the LLM should explain those numbers, not invent them.

---

## AI-6 Grounded Admin Copilot

Admin asks:

> Show unresolved high-priority sanitation cases in W18 older than seven days.

Architecture:

```text
Admin
 ↓
AI intent parser
 ↓
validated query/tool call
 ↓
PostgreSQL
 ↓
results
 ↓
AI explanation
 ↓
UI table/map
```

The model never receives arbitrary unrestricted database credentials.

---

# 12. AI Confidence Policy

Every AI recommendation contains:

- model
- model version
- prompt/schema version
- confidence/quality signal where available
- timestamp
- input references
- output
- human decision

Example:

```text
AI Classification
Road Damage
Confidence: 0.94

Accepted by:
Department Operator #42

Override:
No
```

---

# 13. AI Safety / Governance

AI must:

- recommend, not silently decide consequential municipal actions;
- expose uncertainty;
- retain source evidence;
- allow human override;
- log overrides;
- avoid using protected/sensitive personal attributes for priority;
- avoid citizen reputation scoring;
- avoid autonomous punitive actions.

---

# 14. Multilingual Architecture

Language is an end-to-end concern.

Pipeline:

```text
Citizen voice
 ↓
Language identification
 ↓
Speech-to-text
 ↓
Canonical semantic representation
 ↓
Civic Case
 ↓
Department language rendering
 ↓
Citizen-language response
```

The canonical database stores structured semantic fields rather than translated copies as the source of truth.

Store:

- original language
- original transcript
- canonical structured representation
- translated presentation where needed

---

# 15. Device/Input Architecture

The backend accepts a common `EvidenceItem` abstraction.

Sources:

```text
SMARTPHONE
TABLET
SMARTWATCH
CAMERA
VIDEO
VOICE
DASHCAM
FIELD_WORKER
MUNICIPAL_INSPECTION
SENSOR
IMPORT
```

Each evidence item can carry:

- media
- MIME type
- timestamp
- source device/type
- latitude
- longitude
- accuracy
- uploader
- hash
- case relation

This keeps the backend independent of the client device.

---

# 16. Offline-First Architecture

Citizen app is a PWA.

Use:

- Service Worker
- IndexedDB
- background synchronization where supported
- explicit local outbox

IndexedDB is suitable for storing significant structured data and blobs client-side. Service workers provide the offline-first network/cache boundary. Background Sync can defer failed submissions until connectivity returns, with a fallback required because Background Sync is not universally available. citeturn4search0turn4search1turn4search12

## Local outbox

```text
Draft
 ↓
Queued
 ↓
Uploading
 ↓
Uploaded
 ↓
Server acknowledged
 ↓
Local cleanup
```

Every mutation has an idempotency key.

---

# 17. Low-Bandwidth Architecture

Prioritize:

1. text/status
2. thumbnails
3. compressed image
4. full image
5. video

Media upload uses resumable/presigned upload where practical.

---

# 18. Core End-to-End Data Flow

## 18.1 Citizen report online

```text
Citizen UI
 ↓
Capture Controller
 ↓
Local Validation
 ↓
Media Upload Service
 ↓
API Gateway / FastAPI
 ↓
Case Intake Service
 ↓
PostgreSQL
 ↓
Redis Stream: case.created
 ↓
AI Worker
 ├── transcription
 ├── vision
 ├── classification
 ├── embedding
 └── duplicate candidate search
 ↓
AI result persisted
 ↓
Notification event
 ↓
Citizen UI
```

---

# 19. Offline Data Flow

```text
Citizen UI
 ↓
IndexedDB
 ↓
Outbox
 ↓
Connectivity detected
 ↓
Background Sync / app retry
 ↓
Idempotent API
 ↓
Media upload
 ↓
Case creation
 ↓
AI processing
 ↓
Server acknowledgement
 ↓
Outbox item marked synced
```

---

# 20. Case Fusion Data Flow

```text
New evidence/report
 ↓
Normalize text
 ↓
Generate embedding
 ↓
PostGIS nearby candidate query
 ↓
pgvector semantic candidate query
 ↓
Rule-based candidate scoring
 ↓
AI/reranker when needed
 ↓
Candidate cases
 ↓
Citizen/admin decision
 ↓
Attach to existing case OR create case
```

Candidate generation should be deterministic and bounded before an LLM is invoked.

---

# 21. Work Order Data Flow

```text
Civic Case
 ↓
Assignment
 ↓
Work Order
 ↓
Department
 ↓
Worker
 ↓
Start
 ↓
Evidence
 ↓
Complete
 ↓
Verification
```

---

# 22. Resolution Data Flow

```text
Field Worker
 ↓
After evidence
 ↓
Object Storage
 ↓
Case Evidence
 ↓
Resolution Intelligence
 ↓
Verification Request
 ↓
Citizen
 ├── Confirm
 ├── Partial
 └── Still exists
       ↓
Case status transition
```

---

# 23. Event-Driven Components

Redis Streams are used for asynchronous jobs/events.

Important events:

```text
case.created
case.updated
case.status_changed
case.evidence.added
case.ai_requested
case.ai.completed
case.duplicate_candidate_found
work_order.created
work_order.started
work_order.completed
verification.requested
verification.completed
notification.created
incident.created
```

Redis Streams support append-only event logs and consumer groups with acknowledgements and pending-message handling, making them suitable for background workers in this architecture. citeturn1search0turn1search2

---

# 24. Architectural Style

V1 uses a **modular monolith + asynchronous workers**, not microservices.

Reason:

- hackathon-scale team,
- much lower operational complexity,
- clear domain boundaries,
- easy local development,
- easy deployment,
- sufficient scale for the target.

Logical modules:

```text
Auth
Users
Cases
Evidence
Community
Departments
Work Orders
Notifications
Incidents
Analytics
AI
Search
Geo
Audit
```

These are code modules first.

They are not separate deployable services unless scale later justifies extraction.

---

# 25. High-Level Architecture

```text
                 ┌─────────────────────┐
                 │ Citizen PWA          │
                 └──────────┬──────────┘
                            │ HTTPS
                 ┌──────────▼──────────┐
                 │ Admin Web App        │
                 └──────────┬──────────┘
                            │
                 ┌──────────▼──────────┐
                 │ Overlooker Web App   │
                 └──────────┬──────────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │ FastAPI Backend  │
                  │                  │
                  │ Auth             │
                  │ Cases            │
                  │ Evidence         │
                  │ Workflow         │
                  │ Geo              │
                  │ Analytics        │
                  │ AI orchestration │
                  └───────┬──────────┘
                          │
             ┌────────────┼────────────┐
             │            │            │
             ▼            ▼            ▼
       PostgreSQL       Redis       Object Store
       + PostGIS        Streams      S3-compatible
       + pgvector
             │
             │
             ▼
       AI Worker Pool
             │
       ┌─────┼─────┐
       ▼     ▼     ▼
     Vision Speech Embeddings/
     /LLM         similarity
```

---

# 26. Technology Stack — V1 Lock

## Frontend

| Layer | Technology | V1 version/line | Decision |
|---|---|---:|---|
| Language | TypeScript | 6.0.x | LOCK |
| UI | React | 19.3.x | LOCK |
| Bundler | Vite | 8.1.x | LOCK |
| Routing | React Router | 7.x | LOCK |
| Server state | TanStack Query | 5.x | LOCK |
| Local UI state | Zustand | 5.x | LOCK |
| Styling | Tailwind CSS | 4.3.x | LOCK |
| Icons | Lucide React | current compatible 0.x line | LOCK |
| Maps | MapLibre GL JS | 6.x | LOCK |
| Charts | Recharts | 3.x | LOCK |
| Validation | Zod | 4.x | LOCK |
| PWA | Vite PWA / Workbox | current stable compatible line | LOCK |
| Testing | Vitest + Testing Library | current stable compatible line | LOCK |
| E2E | Playwright | current stable compatible line | LOCK |

Vite 8 introduced the Rolldown-based unified bundler and Vite 8.1 is the latest release identified in the research. React 19.3 is current. TypeScript 7 is now stable, but V1 deliberately uses TypeScript 6.0.x because TypeScript 7's programmatic API transition is still relevant to ecosystem tooling; the project can revisit TS7 after the ecosystem settles. citeturn0search0turn0search11turn7search0

MapLibre GL JS 6 is selected because it is the current major line; v6 is ESM-only and requires the appropriate bundler setup. citeturn11search6turn11search9

---

# 27. Backend Stack

| Layer | Technology | V1 version/line |
|---|---|---:|
| Language | Python | 3.14.x |
| API framework | FastAPI | 0.142.2 |
| ASGI server | Uvicorn | current stable compatible line |
| Validation | Pydantic | 2.x |
| ORM/SQL | SQLAlchemy | 2.0.54 |
| Migrations | Alembic | 1.16.x |
| Async PostgreSQL driver | asyncpg | current stable compatible line |
| HTTP client | httpx | current stable compatible line |
| Task/event processing | Redis Streams | Redis 8.10.x |
| API docs | OpenAPI generated by FastAPI | 3.x |

FastAPI 0.142.2 was released September 30, 2026 and includes native OpenTelemetry support. Python 3.14.8 was released September 30, 2026 as a security/maintenance release. SQLAlchemy 2.0.54 is the current 2.0 maintenance release identified in September 2026. citeturn0search9turn5search6turn8search10

---

# 28. Database Stack

| Layer | Technology | V1 version |
|---|---|---:|
| Database | PostgreSQL | 18.6 |
| Geospatial | PostGIS | 3.6.x stable |
| Vector search | pgvector | 0.8.6 |
| Full text | PostgreSQL FTS | native |
| JSON | PostgreSQL JSONB | native |

PostgreSQL 18.6 is the current supported major release identified in August 2026. PostGIS 3.6 is the stable line; 3.7 was still in release-candidate development in August 2026, so V1 does not depend on 3.7. citeturn8search0turn8search16turn0search12

PostGIS geography supports geodetic coordinates and spatial operations, making it appropriate for location-aware Civic Cases. citeturn1search3

pgvector 0.8.6 is selected for embeddings and similarity search. citeturn0search4

---

# 29. Cache / Event Stack

Redis Open Source 8.10.2 is the researched September 2026 release.

Use Redis for:

- event streams
- job coordination
- short-lived cache
- rate limiting
- distributed locks where necessary
- notification fan-out

Do not use Redis as the system-of-record database.

Redis 8.x provides Streams and consumer groups appropriate for worker processing. citeturn9search1turn1search0

---

# 30. AI Stack

## Provider

OpenAI API behind a dedicated `AIProvider` abstraction.

The rest of CivicConnect must not depend directly on model-specific implementation details.

```text
AIService
   ↓
AIProvider interface
   ↓
OpenAIProvider
```

This preserves the option to introduce another model provider later.

## Capabilities

- multimodal reasoning
- image analysis
- structured extraction
- speech processing
- embeddings
- grounded tool/function calling

OpenAI's current API documentation supports image inputs, structured outputs, embeddings and function/tool calling. Structured Outputs are specifically designed to constrain model responses to a supplied JSON schema. citeturn3search3turn3search0turn3search1turn3search4

## Important

Model names are configuration, not domain logic.

Example:

```env
AI_INTAKE_MODEL=...
AI_ANALYTICS_MODEL=...
AI_EMBEDDING_MODEL=text-embedding-3-small
```

At implementation kickoff, exact model IDs must be validated against the current official model catalogue and recorded in `.env.example`, because model availability can change independently of the application architecture.

---

# 31. Object Storage

Use an S3-compatible object store.

V1 abstraction:

```text
ObjectStorage
 ├── put()
 ├── getSignedUrl()
 ├── delete()
 ├── exists()
 └── checksum()
```

Recommended deployment target:

- Cloudflare R2 or AWS S3

Do not store large media blobs inside PostgreSQL.

PostgreSQL stores metadata and object keys.

---

# 32. Frontend Offline Storage

Use:

- IndexedDB
- service worker
- Workbox background sync
- local outbox

IndexedDB can store structured objects and blobs. Workbox's background-sync module queues failed network requests and retries them when connectivity returns, with a fallback strategy for browsers without native Background Sync. citeturn4search0turn4search2turn4search6

---

# 33. Geospatial Design

Coordinates:

```text WGS84 / EPSG:4326
```

Database:

```text PostGIS geography(Point, 4326)
```

Use cases:

- nearby cases
- radius search
- ward containment
- case clustering
- hotspot detection
- incident boundaries
- route/location context

Example conceptual query:

```sql
SELECT *
FROM civic_cases
WHERE ST_DWithin(
  location,
  ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
  :radius_meters
);
```

---

# 34. Core Database Entities

## User

- id
- name
- phone/email
- role
- preferred_language
- accessibility_preferences
- created_at
- updated_at

## Ward

- id
- name
- boundary geometry
- municipality_id

## Department

- id
- name
- category coverage

## CivicCase

- id
- public_case_id
- title
- canonical_description
- category
- subcategory
- severity
- priority
- status
- location
- ward_id
- department_id
- created_at
- updated_at
- closed_at

## ReportSignal

- id
- case_id
- reporter_id
- original_text
- original_language
- source_type
- created_at

## EvidenceItem

- id
- case_id
- uploader_id
- object_key
- media_type
- hash
- latitude
- longitude
- captured_at
- uploaded_at

## AIAnalysis

- id
- case_id/report_id
- task_type
- model
- prompt_version
- schema_version
- result_json
- confidence/quality
- created_at

## CaseRelation

- id
- case_a
- case_b
- relation_type
- similarity_score
- created_at

## Support

- id
- case_id
- user_id
- created_at

## WorkOrder

- id
- case_id
- department_id
- assigned_worker_id
- priority
- deadline
- status
- created_at
- completed_at

## Verification

- id
- case_id
- citizen_id
- result
- evidence_id
- created_at

## Notification

- id
- user_id
- type
- payload
- read_at
- created_at

## Incident

- id
- title
- description
- geometry
- status
- created_by
- started_at
- ended_at

## AuditEvent

- id
- actor_id
- action
- entity_type
- entity_id
- before_json
- after_json
- created_at

---

# 35. Civic Case State Machine

States:

```text
SUBMITTED
   ↓
AI_PROCESSING
   ↓
NEEDS_REVIEW
   ↓
ASSIGNED
   ↓
WORK_ORDER_CREATED
   ↓
IN_PROGRESS
   ↓
RESOLUTION_SUBMITTED
   ↓
AWAITING_VERIFICATION
   ├───────────────┐
   ↓               ↓
VERIFIED        REOPENED
   ↓               │
RESOLVED ←─────────┘
```

Additional terminal state:

```text
REJECTED
```

A rejected case requires:

- authorized actor
- reason
- audit event

---

# 36. Priority Model

Priority is not simply AI output.

Conceptually:

```text
Priority =
  severity weight
+ affected citizen signal
+ location sensitivity
+ case age
+ recurrence
+ SLA risk
+ incident context
```

The exact formula is configuration-driven.

AI can recommend or explain.

Deterministic business rules decide the operational score.

---

# 37. Duplicate Detection Algorithm

Stage 1:

- same category
- spatial radius
- time window

Stage 2:

- text embedding similarity

Stage 3:

- image similarity if available

Stage 4:

- combined candidate score

Stage 5:

- citizen choice or authorized admin decision

This avoids sending every new report to an expensive LLM.

---

# 38. Recurring Problem Detection

A recurring problem is identified through:

- spatial recurrence
- same category/subcategory
- repeated cases
- time intervals
- repeated resolution/reopening
- infrastructure/asset association where available

Example:

```text
4 water leakage cases
same 150m area
within 8 months
2 previously resolved
1 reopened
```

System surfaces:

> Potential recurring infrastructure problem.

---

# 39. Hotspot Detection

Start with deterministic geospatial aggregation.

Possible approaches:

- grid aggregation
- DBSCAN
- H3-based aggregation if introduced
- rolling baseline comparison

AI can explain detected clusters.

AI should not invent the hotspot itself without evidence.

---

# 40. Analytics Architecture

Operational analytics:

```text
PostgreSQL
 ↓
SQL aggregate queries
 ↓
Analytics API
 ↓
Dashboard
```

AI summaries:

```text
Analytics API
 ↓
validated aggregate result
 ↓
LLM
 ↓
bounded natural-language explanation
```

This keeps factual numbers deterministic.

---

# 41. API Design

Base:

```text
/api/v1
```

## Authentication

```text
POST /auth/request-otp
POST /auth/verify-otp
POST /auth/refresh
POST /auth/logout
GET  /me
```

## Cases

```text
POST   /cases
GET    /cases
GET    /cases/{id}
PATCH  /cases/{id}
POST   /cases/{id}/support
DELETE /cases/{id}/support
POST   /cases/{id}/evidence
POST   /cases/{id}/verify
POST   /cases/{id}/reopen
```

## AI

```text
POST /ai/intake
POST /ai/duplicate-check
POST /ai/triage
POST /ai/resolution-review
POST /ai/copilot/query
```

These may internally enqueue asynchronous work.

## Work Orders

```text
POST  /work-orders
GET   /work-orders
GET   /work-orders/{id}
PATCH /work-orders/{id}
POST  /work-orders/{id}/start
POST  /work-orders/{id}/complete
```

## Analytics

```text
GET /analytics/overview
GET /analytics/trends
GET /analytics/hotspots
GET /analytics/recurrence
GET /analytics/departments
GET /analytics/wards
```

## Incidents

```text
POST /incidents
GET  /incidents
GET  /incidents/{id}
POST /incidents/{id}/cases
PATCH /incidents/{id}
```

---

# 42. API Security

The API must explicitly address:

- broken object-level authorization,
- broken authentication,
- property-level authorization,
- unrestricted resource consumption,
- broken function-level authorization,
- SSRF,
- security misconfiguration,
- API inventory,
- unsafe third-party API consumption.

These map directly to OWASP API Security Top 10 categories. citeturn2search0turn2search6

Application controls should be designed against OWASP ASVS 5.0.0. citeturn2search2

---

# 43. Authentication & Authorization

Use:

```text
Authentication
    ↓
User identity
    ↓
Role
    ↓
Permission
    ↓
Object-level authorization
```

Never trust:

```text
role=admin
```

sent by the client.

The server derives permissions from authenticated identity and database state.

---

# 44. Media Security

Uploads require:

- MIME validation
- size limits
- extension validation
- content inspection where appropriate
- generated object keys
- private object storage
- short-lived signed URLs
- authorization before access
- malware scanning where feasible
- checksum

No public bucket for citizen evidence.

---

# 45. Privacy

Collect the minimum information required.

Separate:

```text
Identity data
Case data
Evidence data
Operational data
Analytics
```

Citizen identity should not be exposed unnecessarily to other citizens.

Community views use privacy-preserving representations.

---

# 46. Audit Logging

Audit events are mandatory for:

- role changes
- case reassignment
- priority override
- category override
- merge/split
- rejection
- resolution
- reopening
- verification
- settings changes
- AI override

Audit records are append-only from the application perspective.

---

# 47. Observability

Use OpenTelemetry-compatible tracing.

Trace:

```text
request
 ↓
database
 ↓
Redis event
 ↓
AI worker
 ↓
notification
```

Metrics:

- API latency
- error rate
- AI latency
- AI failure rate
- queue depth
- case processing time
- media upload failures
- notification delivery
- DB query latency

FastAPI 0.142.0 introduced native OpenTelemetry support, and 0.142.2 is the current release identified during this research. citeturn0search9

---

# 48. Deployment Architecture

## Frontend

Three independently deployable web applications:

```text
citizen.civicconnect...
admin.civicconnect...
overlooker.civicconnect...
```

Recommended hosting:

- Vercel or equivalent static/frontend platform

## Backend

Dockerized FastAPI.

Deploy to:

- DigitalOcean
- Railway
- Render
- AWS
- equivalent container host

## Database

Managed PostgreSQL 18.6 with:

- PostGIS
- pgvector
- automated backups

## Redis

Managed Redis 8.x.

## Object storage

S3-compatible.

---

# 49. Repository Structure

The V1 implementation uses a **single monorepo**. All four team members work against the same directory structure.

This section is an implementation-standardization clarification to the already-frozen V1 architecture. It does not change product scope, APIs, domain entities, AI boundaries, or technology decisions.

```text
civicconnect-v2/
│
├── apps/
│   ├── citizen/             # Citizen mobile-first PWA
│   ├── admin/               # Department/admin operations web app
│   ├── field-worker/        # Field-worker workflow app
│   └── overlooker/          # City intelligence / command center
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── auth/
│   │   ├── cases/
│   │   ├── evidence/
│   │   ├── community/
│   │   ├── departments/
│   │   ├── work_orders/
│   │   ├── incidents/
│   │   ├── analytics/
│   │   ├── notifications/
│   │   ├── geo/
│   │   ├── ai/
│   │   ├── audit/
│   │   └── core/
│   ├── migrations/
│   ├── tests/
│   └── Dockerfile
│
├── ai/
│   ├── training/            # Kaggle notebooks/scripts and experiment configs
│   ├── inference/            # Production inference adapters/pipelines
│   ├── evaluation/           # AI evaluation datasets/scripts/reports
│   └── artifacts/             # Local/generated model artifacts; large files gitignored
│
├── packages/
│   ├── api-client/            # Generated/shared API client from OpenAPI
│   ├── shared-types/          # Shared TypeScript domain types
│   ├── schemas/               # Shared validation schemas where appropriate
│   ├── ui/                    # Shared frontend primitives/design system
│   └── config/                # Shared frontend/build configuration
│
├── infra/
│   ├── docker/
│   ├── compose/
│   └── scripts/
│
├── scripts/                   # Repo-level development/verification scripts
│
├── docs/
│   ├── README.md
│   ├── CivicConnect_v2_V1_System_Design.md
│   ├── COMMON_DIRECTORY_STRUCTURE.md
│   ├── TEAM_INTEGRATION_RULES.md
│   ├── IMPLEMENTATION_PLAN_TANUJ.md
│   ├── IMPLEMENTATION_PLAN_PARTH.md
│   ├── IMPLEMENTATION_PLAN_KRRISH.md
│   └── IMPLEMENTATION_PLAN_VEDANT.md
│
├── .env.example
├── .gitignore
└── README.md
```

### Repository ownership rules

- `docs/` is the shared source-of-truth area. Team members read it; implementation AI tools must treat the system design and assigned plans as **read-only**.
- `apps/citizen`, `apps/admin`, `apps/field-worker`, and `apps/overlooker` are separate frontend applications but share backend contracts and shared packages.
- `backend/` is the system-of-record API and workflow layer.
- `ai/` contains AI training/evaluation/inference work. AI logic is not duplicated independently inside each frontend.
- `packages/` contains reusable contracts/primitives, not app-specific business logic.
- Large model artifacts, datasets, credentials, `.env` files, and generated secrets are never committed.
- Existing prototype directories (`citizen/`, `Admin_new/`, `Overlooker/`) may be migrated into `apps/` after inspection and verification; do not delete working code merely to satisfy the new folder structure.

# 50. Frontend Architecture

Each app follows:

```text
pages/routes
 ↓
feature components
 ↓
hooks
 ↓
TanStack Query
 ↓
API client
 ↓
backend
```

Local UI state:

```text
Zustand
```

Server state:

```text
TanStack Query
```

Do not place server entities into one giant React Context.

The old `AppContext` architecture should be retired.

TanStack Query is specifically designed for server-state caching, deduplication, refetching, mutation handling and cache lifecycle management. citeturn10search5

---

# 51. Shared API Contract

Backend publishes OpenAPI.

Generate TypeScript API types/client.

Goal:

```text
Python schema
      ↓
OpenAPI
      ↓
generated TS client
      ↓
all frontend apps
```

No manually duplicated request/response interfaces.

---

# 51A. API Contract Specification

This section freezes the **V1 API contract surface**. Endpoint names, HTTP methods, major request/response shapes, authentication rules, idempotency behavior, pagination conventions, and error semantics are part of the implementation contract.

The backend remains the system of record. All clients — Citizen PWA, Admin, Field Worker, and Overlooker — consume the same versioned API surface.

## 51A.1 API conventions

Base path:

```text
/api/v1
```

Content types:

```text
application/json
multipart/form-data   # media upload endpoints only
```

Authentication:

```text
Authorization: Bearer <access-token>
```

Required mutation header:

```text
Idempotency-Key: <client-generated-uuid>
```

Recommended request correlation header:

```text
X-Request-ID: <uuid>
```

Pagination:

```json
{
  "items": [],
  "next_cursor": "opaque-cursor-or-null"
}
```

Errors use one stable envelope:

```json
{
  "error": {
    "code": "CASE_NOT_FOUND",
    "message": "The requested civic case does not exist.",
    "details": {},
    "request_id": "uuid"
  }
}
```

Clients must branch on `error.code`, not on human-readable `message`.

## 51A.2 Authentication and session

### `POST /auth/register`

Creates a citizen account.

Request:

```json
{
  "name": "string",
  "email": "string|null",
  "phone": "string|null",
  "preferred_language": "string"
}
```

Response `201`:

```json
{
  "user": { "id": "uuid", "name": "string", "role": "CITIZEN" },
  "access_token": "string",
  "refresh_token": "string"
}
```

### `POST /auth/login`

Request:

```json
{
  "identifier": "string",
  "password": "string"
}
```

Response: same session shape as registration.

### `POST /auth/refresh`

Request:

```json
{ "refresh_token": "string" }
```

Response:

```json
{ "access_token": "string", "refresh_token": "string" }
```

### `GET /auth/me`

Returns the authenticated user's profile, role, language and access scope.

## 51A.3 Citizen profile and preferences

### `GET /me`

Returns the current user's profile.

### `PATCH /me`

Request may contain:

```json
{
  "name": "string",
  "preferred_language": "string",
  "accessibility": {
    "large_text": true,
    "high_contrast": false,
    "reduced_motion": true,
    "voice_playback": true
  }
}
```

### `GET /me/notifications`

Returns cursor-paginated notifications.

### `POST /me/notifications/{notification_id}/read`

Marks a notification as read. Idempotent.

## 51A.4 Civic case creation and retrieval

### `POST /cases`

Creates a civic case from structured client input.

Request:

```json
{
  "client_case_id": "uuid",
  "title": "string|null",
  "description": "string|null",
  "category": "string|null",
  "location": {
    "latitude": 19.0760,
    "longitude": 72.8777,
    "accuracy_m": 12.0
  },
  "observed_at": "ISO-8601|null",
  "language": "string",
  "source": "CITIZEN",
  "evidence_ids": ["uuid"]
}
```

Response `201`:

```json
{
  "case": {
    "id": "uuid",
    "case_number": "CC-2026-000001",
    "status": "SUBMITTED",
    "category": "string",
    "priority": "NORMAL",
    "location": {},
    "created_at": "ISO-8601",
    "updated_at": "ISO-8601"
  }
}
```

The server owns authoritative status, priority, assignment and timestamps.

### `GET /cases/{case_id}`

Returns the case, current status, location, category, priority, reporter/contributor relationships, evidence metadata, assignments and permitted timeline entries.

### `GET /cases`

Citizen scope returns cases visible to the authenticated citizen.

Supported query parameters:

```text
status
category
from
until
cursor
limit
sort
```

### `PATCH /cases/{case_id}`

Only fields explicitly permitted by the caller's role may be changed. Citizen edits are restricted to the allowed pre-processing state.

### `POST /cases/{case_id}/contributors`

Adds a permitted contributor/supporter relationship.

Request:

```json
{ "user_id": "uuid", "role": "CONTRIBUTOR" }
```

## 51A.5 AI intake

### `POST /cases/intake/analyze`

Converts text/audio/image evidence into a **proposed** structured Civic Case. It does not create or close a case by itself.

Request:

```json
{
  "text": "string|null",
  "evidence_ids": ["uuid"],
  "language_hint": "string|null",
  "location": { "latitude": 0.0, "longitude": 0.0 }
}
```

Response:

```json
{
  "proposal": {
    "title": "string",
    "description": "string",
    "category": "string",
    "severity": "LOW|MEDIUM|HIGH|CRITICAL",
    "location": {},
    "language": "string"
  },
  "confidence": 0.0,
  "warnings": [],
  "requires_confirmation": true
}
```

The citizen must be able to review/correct the proposal before submission.

## 51A.6 Evidence and media

### `POST /evidence/upload-init`

Creates a media upload session.

Request:

```json
{
  "filename": "string",
  "mime_type": "image/jpeg",
  "size_bytes": 123456,
  "sha256": "hex-string",
  "source": "SMARTPHONE",
  "captured_at": "ISO-8601|null",
  "location": { "latitude": 0.0, "longitude": 0.0 }
}
```

Response:

```json
{
  "evidence_id": "uuid",
  "upload_url": "signed-url",
  "expires_at": "ISO-8601"
}
```

### `POST /evidence/{evidence_id}/complete`

Confirms upload completion. Server validates object existence, checksum, MIME type and size before making evidence available to case workflows.

### `GET /evidence/{evidence_id}`

Returns metadata and a short-lived signed retrieval URL when authorized.

Media bytes are not stored in PostgreSQL.

## 51A.7 Case fusion / duplicates

### `POST /cases/{case_id}/fusion/analyze`

Runs duplicate/correlation analysis.

Response:

```json
{
  "matches": [
    {
      "case_id": "uuid",
      "similarity": 0.0,
      "signals": {
        "semantic": 0.0,
        "geospatial": 0.0,
        "temporal": 0.0,
        "visual": 0.0
      }
    }
  ],
  "recommendation": "POSSIBLE_DUPLICATE|RELATED|NO_MATCH"
}
```

This endpoint produces a recommendation; case merging remains an authorized workflow and is auditable.

## 51A.8 AI triage

### `POST /cases/{case_id}/triage/analyze`

Response:

```json
{
  "recommendation": {
    "severity": "HIGH",
    "priority": "URGENT",
    "department": "WATER",
    "sla_hours": 24
  },
  "confidence": 0.0,
  "reasons": ["string"],
  "warnings": []
}
```

AI recommendations never directly override authorized human decisions.

### `POST /cases/{case_id}/triage/decision`

Records the authorized triage decision.

Request:

```json
{
  "severity": "HIGH",
  "priority": "URGENT",
  "department_id": "uuid",
  "sla_hours": 24,
  "reason": "string"
}
```

## 51A.9 Assignment and work orders

### `POST /cases/{case_id}/work-orders`

Admin/authorized dispatcher creates a field-worker work order.

Request:

```json
{
  "assignee_id": "uuid",
  "instructions": "string",
  "due_at": "ISO-8601"
}
```

### `GET /work-orders`

Role-scoped list of assigned/available work orders.

### `GET /work-orders/{work_order_id}`

Returns original case context, evidence, location, priority, SLA, instructions and current work state.

### `POST /work-orders/{work_order_id}/start`

Records work start time and worker identity.

### `POST /work-orders/{work_order_id}/complete`

Request:

```json
{
  "notes": "string",
  "resolution_evidence_ids": ["uuid"]
}
```

Completing work does **not** automatically close the civic case. It transitions the case into the configured verification workflow.

## 51A.10 Citizen verification

### `POST /cases/{case_id}/verification`

Request:

```json
{
  "result": "YES|PARTIAL|STILL_OCCURRING|NO",
  "comment": "string|null",
  "evidence_ids": ["uuid"]
}
```

The server records the verifier, timestamp and evidence. A permitted `STILL_OCCURRING` result can reopen/escalate the case according to policy.

## 51A.11 Case timeline

### `GET /cases/{case_id}/timeline`

Returns an immutable, role-filtered chronological event stream:

```json
{
  "items": [
    {
      "id": "uuid",
      "event_type": "TRIAGE_DECIDED",
      "actor_id": "uuid",
      "timestamp": "ISO-8601",
      "metadata": {}
    }
  ],
  "next_cursor": null
}
```

## 51A.12 Maps and geospatial queries

### `GET /map/cases`

Parameters:

```text
bbox=minLon,minLat,maxLon,maxLat
category
status
priority
from
until
limit
```

Returns lightweight case markers. Full case payloads are fetched separately.

### `GET /map/hotspots`

Returns server-computed hotspot geometries and supporting aggregate metrics for the authorized scope.

### `GET /map/recurring-problems`

Returns recurring-problem clusters with category, geography, time window, recurrence count and linked case IDs where authorized.

## 51A.13 Analytics

### `GET /analytics/overview`

Returns aggregate operational metrics such as open cases, resolution time, SLA risk and category distribution.

### `GET /analytics/departments/{department_id}`

Returns department-scoped workload, SLA and resolution metrics.

### `GET /analytics/incidents`

Returns incident summaries and status for authorized users.

Analytics endpoints return aggregates rather than unrestricted raw citizen data.

## 51A.14 Incident mode

### `POST /incidents`

Creates an incident grouping related cases.

Request:

```json
{
  "title": "string",
  "description": "string",
  "category": "string",
  "boundary": "GeoJSON geometry",
  "case_ids": ["uuid"]
}
```

### `GET /incidents/{incident_id}`

Returns incident boundary, timeline, affected cases, departments, work orders and status.

### `POST /incidents/{incident_id}/cases`

Adds an authorized case to an incident.

## 51A.15 Admin AI Copilot

### `POST /copilot/query`

Request:

```json
{
  "query": "string",
  "scope": {
    "ward_id": "uuid|null",
    "department_id": "uuid|null",
    "from": "ISO-8601|null",
    "until": "ISO-8601|null"
  }
}
```

Response:

```json
{
  "answer": "string",
  "data": [],
  "citations": [
    { "type": "CASE|ANALYTIC|INCIDENT", "id": "uuid" }
  ],
  "warnings": []
}
```

The copilot must retrieve authorized CivicConnect data/tools before answering. It must not fabricate database facts.

## 51A.16 Offline synchronization

### `POST /sync/mutations`

Accepts an ordered batch of locally queued idempotent mutations.

Request:

```json
{
  "device_id": "uuid",
  "mutations": [
    {
      "idempotency_key": "uuid",
      "client_timestamp": "ISO-8601",
      "operation": "CREATE_CASE",
      "payload": {}
    }
  ]
}
```

Response:

```json
{
  "results": [
    {
      "idempotency_key": "uuid",
      "status": "APPLIED|ALREADY_APPLIED|REJECTED",
      "server_resource_id": "uuid|null",
      "error": null
    }
  ],
  "server_cursor": "opaque-cursor"
}
```

The endpoint is explicitly idempotent. A retried mutation must never create a second case or duplicate side effect.

### `GET /sync/changes?cursor=<cursor>`

Returns authorized changes since the supplied cursor for client reconciliation.

## 51A.17 Health and operational endpoints

### `GET /health/live`

Process liveness only.

### `GET /health/ready`

Readiness including required infrastructure dependencies.

These endpoints expose no citizen data.

## 51A.18 Role and authorization matrix

| Capability | Citizen | Field Worker | Admin | Overlooker |
|---|---:|---:|---:|---:|
| Create case | Yes | Yes | Yes | No |
| View own cases | Yes | Limited | Yes | Aggregated |
| View assigned work | No | Yes | Yes | No |
| Triage decision | No | No | Yes | No |
| Create work order | No | No | Yes | No |
| Submit resolution evidence | No | Yes | Yes | No |
| Verify resolution | Yes | No | Yes | No |
| Reopen case through verification | Yes* | No | Yes | No |
| View city analytics | Limited | Limited | Yes | Yes |
| Run grounded copilot | No | No | Yes | Yes, scoped |
| Manage users/settings | No | No | Yes | No |

`*` Subject to case ownership/verification policy.

## 51A.19 API versioning and compatibility

V1 uses `/api/v1`. Breaking changes require a new API version rather than silently changing an existing contract.

Additive response fields are considered backward-compatible. Clients must ignore unknown response fields.

Contract tests must validate the OpenAPI document against backend routes and generated frontend client types.

# 52. Frontend Offline State

State separation:

```text
Server state → TanStack Query
UI state → Zustand
Offline data → IndexedDB
Outbox → IndexedDB
Auth/session → secure browser mechanism
```

---

# 53. Notification Architecture

Events:

```text
case assigned
case updated
verification requested
case resolved
incident created
work order assigned
```

Flow:

```text
Domain event
 ↓
Notification worker
 ↓
Notification DB
 ↓
Web/PWA notification
```

Channels:

- in-app
- web push
- email/SMS later

---

# 54. Search Architecture

Search fields:

- case ID
- title
- category
- location
- ward
- department
- status

Semantic search:

- embeddings

Full-text:

- PostgreSQL FTS

Geospatial:

- PostGIS

No external search cluster in V1.

---

# 55. Performance Targets

Initial engineering targets:

### API

- p95 normal CRUD API < 500 ms excluding AI/media processing

### Case creation

- acknowledgement < 1 s after valid metadata upload, excluding asynchronous AI

### AI intake

- asynchronous; UI shows processing state

### Map

- viewport queries only
- cluster large result sets

### Offline

- report creation must remain usable without network

These are engineering targets, not guaranteed production SLAs.

---

# 56. Testing Strategy

## Unit

- domain logic
- priority calculation
- state transitions
- authorization
- duplicate candidate scoring

## Integration

- PostgreSQL
- PostGIS
- Redis
- object storage
- AI provider adapter

## API

- OpenAPI contract
- authentication
- authorization
- invalid inputs
- rate limits

## Frontend

- component tests
- workflow tests

## E2E

Critical flows:

1. citizen login
2. online report
3. offline report → reconnect
4. AI intake
5. duplicate suggestion
6. admin assignment
7. work order
8. worker resolution
9. citizen verification
10. reopen

---

# 57. AI Evaluation

Before trusting AI in the demo, create a small labelled evaluation set.

Examples:

```text
100–300 civic reports
```

Evaluate:

- category accuracy
- subcategory accuracy
- routing accuracy
- severity agreement
- duplicate precision/recall
- multilingual extraction quality
- structured-output validity

AI changes require regression tests.

---

# 58. Demo Dataset

V1 should include a seeded synthetic city dataset.

Example:

```text
10 wards
8 departments
500+ Civic Cases
multiple categories
duplicate groups
recurring problems
SLA violations
resolved cases
reopened cases
active incidents
```

This makes Admin and Overlooker dashboards meaningful without fabricating real civic claims.

All demo data must be explicitly labelled as synthetic/demo data.

---

# 59. Recommended Hackathon Demo Flow

The strongest demonstration should be one continuous case.

## Scene 1

Citizen sees:

> Large pothole near school.

## Scene 2

Citizen records Marathi/Hindi/English voice + photo + GPS.

## Scene 3

Network is disabled.

Submission is saved offline.

## Scene 4

Network returns.

Submission syncs automatically.

## Scene 5

AI:

```text
Road damage
Pothole
High severity
Road Maintenance
```

## Scene 6

System finds:

> Existing case 74m away — 92% similarity.

Citizen supports existing case.

## Scene 7

Admin sees:

> Case now has 7 supporting citizens.

## Scene 8

Admin creates work order.

## Scene 9

Field worker receives task and uploads after-photo.

## Scene 10

Resolution evidence is submitted.

## Scene 11

Citizen receives:

> Is the issue actually fixed?

Citizen selects:

> Yes.

## Scene 12

Overlooker shows:

> Ward hotspot reduced after resolution.

This demonstrates the entire platform rather than isolated features.

---

# 60. Innovation Stack

The project should communicate innovation at several layers.

## Layer 1 — Access

- multimodal
- multilingual
- voice-first
- accessible
- offline
- low-bandwidth

## Layer 2 — Intelligence

- AI intake
- case fusion
- triage
- resolution intelligence

## Layer 3 — Workflow

- Civic Case
- Work Order
- field worker
- SLA
- verification

## Layer 4 — Collective Intelligence

- supporting citizens
- evidence aggregation
- recurring issues
- hotspots

## Layer 5 — City Intelligence

- analytics
- anomalies
- incidents
- department workload
- grounded admin copilot

---

# 61. What We Explicitly Avoid

CivicConnect must not become:

### "Chatbot + CRUD"

AI must operate inside workflows.

### "Social media for complaints"

Community exists to improve evidence and civic coordination.

### "AI decides everything"

Human authority remains in consequential decisions.

### "Dashboard full of random charts"

Every metric answers a real operational question.

### "Microservices everywhere"

V1 is modular monolith + workers.

### "Huge database of unnecessary personal information"

Minimize PII.

### "Fake predictive AI"

Only make predictive claims after evaluation data supports them.

---

# 62. Future Extension Points

The architecture leaves room for:

## Smartwatch

Quick signal:

```text
GPS + voice + timestamp
```

## Municipal sensors

```text
sensor signal
→ evidence/event
→ Civic Case correlation
```

## Dashcams

Repeated road observations.

## Inspection teams

Field-generated cases.

## Existing municipal systems

API ingestion.

## Citizen mobile experience

**V1 citizen frontend is a mobile-first Progressive Web App (PWA), not a separate native Android/iOS application.**

The existing CivicConnect prototype is a React/Vite web application. For V2, the citizen client is explicitly specified as a responsive, touch-first PWA that works from a phone browser and can be installed to the home screen. The same client must support tablet and desktop layouts without creating a second citizen frontend codebase.

V1 mobile requirements:

- mobile-first layouts
- touch-friendly controls
- camera/photo capture
- microphone/audio capture
- GPS/location access
- installable PWA
- offline reporting and outbox
- push notifications where supported
- low-bandwidth mode
- accessibility settings
- responsive tablet/desktop adaptation

A native Android/iOS application is **not required for V1**. The backend/API and `EvidenceItem` abstraction are intentionally client-independent so a native application can be introduced later without redesigning the Civic Case Engine.

## IoT

Future sensor adapters.

---

# 63. Research-Backed Architectural Decisions

## 63.1 PostgreSQL + PostGIS

Chosen because CivicConnect is inherently relational and spatial.

PostGIS provides geography support for geodetic coordinates and spatial operations. citeturn1search3

## 63.2 pgvector

Chosen to keep semantic case matching inside PostgreSQL instead of introducing a separate vector database.

pgvector supports similarity search and has current PostgreSQL 18 compatibility work. citeturn0search4

## 63.3 Redis Streams

Chosen for asynchronous workflow/event processing because Streams support consumer groups, acknowledgement and pending-message recovery. citeturn1search0turn1search2

## 63.4 PWA + IndexedDB + Service Worker

Chosen to make citizen reporting resilient to unreliable connectivity. IndexedDB supports structured client-side data including blobs; service workers provide the offline cache/request boundary. citeturn4search0turn4search1

## 63.5 Background Sync

Used as an enhancement, not the sole offline mechanism, because browser support is not universal. citeturn4search12

## 63.6 Structured AI outputs

Chosen because civic intake needs machine-consumable fields rather than free-form prose. OpenAI Structured Outputs can enforce JSON-schema adherence. citeturn3search0

## 63.7 Embeddings

Chosen for semantic similarity, clustering and anomaly-oriented workflows. citeturn3search1

## 63.8 API security

OWASP API Security Top 10 is used as the minimum API security checklist; ASVS 5.0.0 is the application security verification baseline. citeturn2search0turn2search2

---

# 64. Version Policy

V1 is not allowed to silently drift with package updates.

Rules:

1. Exact versions are committed to lockfiles.
2. Major/minor version lines listed in this document are architectural decisions.
3. Security patches may be applied without a product redesign.
4. Major version upgrades require a V1 change review.
5. AI model IDs are configuration and must be revalidated at implementation kickoff.
6. Infrastructure images are pinned.
7. Database major version remains PostgreSQL 18 for V1.
8. PostGIS remains 3.6.x stable for V1.
9. No production dependency may use `latest`.

---

# 65. V1 Review Process

Maximum three rounds.

## Round 1 — Architecture Review

Review:

- product scope
- personas
- case model
- AI boundaries
- page structure
- backend architecture
- data model
- technology choices

Output:

- corrections
- missing capabilities
- contradictions

## Round 2 — Implementation Review

Review:

- API contracts
- database schema
- state machines
- exact UI flows
- failure handling
- deployment
- testing

Output:

- implementation-level corrections

## Round 3 — Freeze Review

Review:

- final architecture
- final page list
- final stack
- final API
- final entities
- final AI modules
- final security rules

After Round 3:

> **V1 IS LOCKED.**

Implementation should then follow the document rather than continuously reinventing the product.

---

# 66. Definition of Done for V1 Architecture

V1 is considered specification-complete when:

- every user role has a defined workflow;
- every major page has defined purpose, UI, behaviour and backend dependency;
- every Civic Case state has defined transitions;
- every AI capability has defined input/output/human-control boundaries;
- every major database entity is defined;
- every major API family is defined;
- offline synchronization is defined;
- media handling is defined;
- multilingual flow is defined;
- geospatial flow is defined;
- security controls are defined;
- deployment architecture is defined;
- testing strategy is defined;
- technology versions are locked;
- the demo flow is coherent end-to-end.

---

# 67. Final V1 Architecture Summary

```text
                         CIVICCONNECT V2
                              │
       ┌──────────────────────┼──────────────────────┐
       │                      │                      │
    CITIZEN                 ADMIN               OVERLOOKER
       │                      │                      │
       │                      │                      │
       └──────────────────────┼──────────────────────┘
                              │
                         HTTPS / API
                              │
                    ┌─────────▼─────────┐
                    │     FastAPI       │
                    │  Modular Monolith │
                    └─────────┬─────────┘
                              │
        ┌─────────────────────┼───────────────────────┐
        │                     │                       │
        ▼                     ▼                       ▼
 PostgreSQL              Redis Streams          Object Storage
 + PostGIS               + workers              media/evidence
 + pgvector
        │                     │
        └──────────┬──────────┘
                   │
             AI Orchestrator
                   │
       ┌───────────┼────────────┐
       ▼           ▼            ▼
   Multimodal   Embeddings   Analytics
     Intake       /Fusion      Intelligence
       │           │            │
       └───────────┼────────────┘
                   │
              CIVIC CASE
                   │
              WORK ORDER
                   │
             FIELD WORKER
                   │
              RESOLUTION
                   │
          CITIZEN VERIFICATION
                   │
            CITY INTELLIGENCE
```

---

# 68. Reference Sources

### Official technology references

1. React 19.3 — React documentation and release announcement.
   - https://react.dev/versions
   - https://react.dev/blog/2026/09/09/react-19-3

2. Vite 8 / 8.1.
   - https://vite.dev/blog/announcing-vite8
   - https://vite.dev/blog/announcing-vite8-1

3. TypeScript 7.
   - https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/

4. FastAPI 0.142.x.
   - https://fastapi.tiangolo.com/release-notes/

5. Python 3.14.8.
   - https://www.python.org/downloads/release/python-3148/

6. PostgreSQL 18.6.
   - https://www.postgresql.org/docs/18.6/

7. PostGIS 3.6.
   - https://postgis.net/2025/09/PostGIS-3.6.0/

8. pgvector.
   - https://github.com/pgvector/pgvector/blob/master/CHANGELOG.md

9. Redis Streams.
   - https://redis.io/docs/latest/develop/data-types/streams/

10. MapLibre GL JS 6.
    - https://maplibre.org/maplibre-gl-js/docs/
    - https://maplibre.org/maplibre-gl-js/docs/guides/v5-to-v6-migration-guide/

11. Tailwind CSS 4.3.
    - https://tailwindcss.com/blog

12. TanStack Query.
    - https://tanstack.com/query/v5

13. IndexedDB / Service Workers.
    - https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API
    - https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers

14. Workbox Background Sync.
    - https://developer.chrome.com/docs/workbox/retrying-requests-when-back-online/

### AI references

15. OpenAI Structured Outputs.
    - https://developers.openai.com/api/docs/guides/structured-outputs

16. OpenAI Images / Vision.
    - https://developers.openai.com/api/docs/guides/images-vision

17. OpenAI Embeddings.
    - https://developers.openai.com/api/docs/guides/embeddings

18. OpenAI Responses API.
    - https://developers.openai.com/api/reference/cli/resources/responses/methods/create

### Security references

19. OWASP API Security Top 10 — 2023.
    - https://api-security.owasp.org/editions/2023/en/0x11-t10/

20. OWASP ASVS 5.0.0.
    - https://owasp.org/projects/asvs

### Project source

21. CivicConnect repository.
    - https://github.com/tanujb03/SIH2025_CivicConnect

---

# 69. V1 Decision Record

**Decision:** Do not begin implementation from ad-hoc feature prompts.

**Decision:** First freeze the product/system design through a maximum of three review rounds.

**Decision:** Preserve the existing CivicConnect frontend as the starting prototype, but redesign its state/data architecture around the Civic Case model.

**Decision:** Build a modular monolith backend with asynchronous workers.

**Decision:** PostgreSQL + PostGIS + pgvector is the system of record and semantic/geospatial data layer.

**Decision:** Redis Streams is the event/job backbone.

**Decision:** AI is an embedded intelligence layer, not a standalone chatbot.

**Decision:** Citizen reporting is multimodal, multilingual, accessible, offline-first and device-independent.

**Decision:** Resolution requires evidence and citizen verification.

**Decision:** Overlooker becomes City Intelligence / Command Center.

**Decision:** V1 ends after three review rounds and is then locked.

### Final Freeze Record — 2026-10-01

**Round 3 status:** COMPLETE.

The final verification checked:

- all previously agreed product capabilities and innovation ideas;
- citizen, admin, field-worker and city-intelligence workflows;
- multimodal, multilingual, accessibility and offline-first requirements;
- Civic Case lifecycle, fusion, triage, work-order, resolution and verification flows;
- AI module boundaries and human-oversight requirements;
- recurring-problem, hotspot, incident and analytics capabilities;
- evidence integrity, abuse prevention, RBAC, auditability and privacy boundaries;
- backend, database, event, storage, frontend and deployment architecture;
- future-device and sensor extension points without incorrectly making them mandatory V1 scope;
- testing, observability, performance and implementation constraints;
- consistency between the frozen feature scope and the selected technology stack.

**Result:** No material missing capability or architecture contradiction was identified.

**Freeze rule:** New features, architectural substitutions, major dependency changes, or changes to core Civic Case semantics after this point require an explicit V1 change review. Minor implementation details may be resolved during implementation only when they do not contradict this specification. AI model IDs remain implementation-time configuration and must be revalidated at kickoff as already specified in the version policy.

**V1 is officially frozen.**

---

## END OF CIVICCONNECT V2 — V1 SYSTEM DESIGN DOCUMENT — LOCKED
