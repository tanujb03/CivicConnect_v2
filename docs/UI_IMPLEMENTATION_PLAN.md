# CivicConnect UI Implementation Plan — Admin and Overlooker

Oct 3, 2026 · @Tanuj Bhide

## How to use this plan

This plan turns the approved Direction A designs into code for the Admin (A01–A13) and Overlooker (O01–O06) web apps, and Antigravity builds only what is written here. The Citizen and Field Worker apps are Expo and follow later with the same tokens.

**Design references (open these beside the plan):**

*   [Admin canvas, A01–A13](#)
*   [Overlooker canvas, O01–O06](#)
*   [CivicConnect Design System](#) (tokens, brand book, six component cards)
*   [Direction A/B and Krackerz research canvas](#) (why A won, what was measured)

**Rules for every Antigravity session:**

1.  Data comes from the frozen contract (§51A) and the backend OpenAPI. Visuals come from this plan. Numbers in the mockups are real demo-city values; never paste them into code.
2.  Build tokens and shared primitives first (sections 2–4), then screens. Do not restyle a screen before its primitives exist.
3.  No hand-written API types. Use `packages/api-client`, and keep fetching inside hooks so components stay pure.
4.  Add primitives to `packages/ui` and import them. Do not rewrite a page that Parth or Vedant is editing; coordinate first.
5.  Every screen ships loading, empty, error and degraded-AI states. The mockups show the degraded states in dashed or yellow boxes.
6.  AI versus human is never ambiguous: human or rules decisions are solid chips, AI suggestions are dashed chips, AI-written text sits on the wine panel with the rosette badge.
7.  Motion is on, and every animation honours `prefers-reduced-motion` (section 3).
8.  Keep the current stack: React 18, Vite 5, Tailwind 3, Leaflet. Do not upgrade libraries or switch to MapLibre before submission.
9.  The mockups are references, not pixel specs. Match structure, tokens, copy tone and behaviour.

## Design system to code

Put every token in one CSS file (`packages/ui/tokens.css`) and extend the Tailwind theme from it, so both web apps and the later Expo apps read the same names. Source of truth: the [Design System](#).

```css
:root{
--ground:#F7F6F0; --surface:#FFFFFF; --ink:#161616; --muted:#5C5A52; --dot:#D8D5C6;
--wine:#580D14; --on-wine:#F7F6F0;
--fire:#CF2B09; --on-fire:#FFFFFF; --rust:#A52207; --rust-deep:#7C1A06;
--lime:#C8FF2E; --amber:#FFB938; --lime-tint:#F3FFC4;
--heat-1:#F3FFC4; --heat-2:#DFF58A; --heat-3:#FFC27A; --heat-4:#E8532B; --heat-5:#580D14;
--radius-sm:8px; --radius-md:12px; --radius-lg:18px; --radius-xl:22px;
--shadow-hard:3px 3px 0 #161616; --shadow-card:5px 5px 0 #161616; --shadow-lift:8px 9px 0 #161616;
--font-display:'Dela Gothic One','Geist',sans-serif;
--font-sans:'Geist','DM Sans',system-ui,sans-serif;
--font-mono:'JetBrains Mono',ui-monospace,monospace;
--font-script:'Yellowtail',cursive;
}
[data-theme="dark"]{
--ground:#161616; --surface:#231F1E; --ink:#F7F6F0; --muted:#B9B5A8; --dot:#2C2826;
--wine:#7A1B26; --fire:#FF5A3C; --on-fire:#161616; --rust:#C2410C; --rust-deep:#9A3412;
--lime-tint:#2E3A0F;
--shadow-hard:3px 3px 0 #F7F6F0; --shadow-card:5px 5px 0 #F7F6F0; --shadow-lift:8px 9px 0 #F7F6F0;
}
body{background:radial-gradient(var(--dot) 1.2px,transparent 1.4px) 0 0/22px 22px,var(--ground);color:var(--ink);font-family:var(--font-sans)}
```

Fonts load from Google Fonts: Dela Gothic One, Geist (400, 500, 600), DM Sans (fallback), JetBrains Mono (500), Yellowtail. Dela Gothic One stands in for Krackerz's unlicensed display face; keep it behind the `--font-display` variable so it can be swapped in one line.

Tailwind: extend `colors` with the token names (`ground`, `surface`, `ink`, `muted`, `wine`, `fire`, `rust`, `lime`, `amber`), `borderRadius` with `sm`, `md`, `lg`, `xl`, `boxShadow` with `hard`, `card`, `lift`, and `fontFamily` with `display`, `sans`, `mono`, `script`. Every colour in the app comes from these names, never raw hex.

**Colour rules that decide meaning:**

*   URGENT priority = `fire` fill with `on-fire` text. HIGH = `amber` fill with `ink` text. NORMAL and LOW = `ink` outline only. The word is always printed.
*   Text on `wine` is `on-wine`; text on `fire` is `on-fire`. Never `ink`, because ink turns cream in the dark theme and fails contrast.
*   Lime always carries `ink` text, never white.
*   Heat steps 1 to 5 differ in lightness, so the scale reads without colour.
*   Cards: `surface`, 2px `ink` outline, `radius-lg`, `shadow-card`. No gradients, no blur, no left-border accents.
*   Dark theme exists for the Overlooker wall screen only; default is light.

## Motion spec

Motion is part of the identity, measured from the start-states on krackerz.com, and it is deliberately generous. Use CSS for micro-motion and `motion` (the framer-motion package) only for route changes and list entrances. The canvases already contain working CSS for every row below; copy it from the Admin canvas.

| Name | Where | Exact spec | Build with |
| :--- | :--- | :--- | :--- |
| Fade-up | Cards, rows, sections on load | from translateY(48px), opacity 0; 0.8s; `cubic-bezier(.16,1,.3,1)`; stagger 40–80 ms | CSS keyframes with `animation-delay` from an index variable |
| Headline pop | One page title per screen | from translateY(-10px) scale(1.4) rotate(.5deg) skewX(-5deg) skewY(2deg); 0.9s; `cubic-bezier(.34,1.56,.64,1)` | CSS keyframes |
| KPI counter | Every KPI number | counts 0 to value in 1.8s, `cubic-bezier(.16,1,.3,1)`; figure comes from the API | CSS `@property --n` integer counter, or `@number-flow/react` if the figure must update live |
| Ticker | Under the page header | translateX(-50%) loop, 46s linear; pauses on hover; tilted -0.6 degrees; items only from real incidents and hotspots | CSS, two identical groups |
| Pulse ring | Critical KPI only | 3px ring scale .97 to 1.1, opacity .8 to 0, 1.9s loop | CSS `::after` |
| Bars grow | Bar and meter charts | scaleY or scaleX from the base, 1s, stagger 45–80 ms | CSS transform-origin bottom or left |
| Typed AI lines | AI summary panels | `steps(64)` width reveal, 1.7s, lines start 1.2s apart | CSS width animation |
| Sticker fly-in | One sticker per section | from translate(-180px,-120px) scale(.5) rotate(-19deg); 1s; ends at rotate(-3deg) | CSS |
| Rosette | AI badge, critical badge | continuous rotation, 16s linear | CSS |
| Button roll | Every primary button | label rolls up on hover (0.35s); arrow chip rotates -45 degrees | CSS two stacked spans |
| Card lift | Every card | hover: translate(-2px,-4px), shadow grows to `shadow-lift`; 0.25s | CSS |
| Intro curtain | Login and first load per session | wine panel with rosette and wordmark, slides up after 0.5s over 1.3s | CSS, shown once using `sessionStorage` |
| Route change | Between pages | opacity and 24px rise, 0.4s | `motion` `AnimatePresence` |

**Rules that keep it safe:**

*   `prefers-reduced-motion: reduce` turns every animation and transition off and shows the final state, including the final counter value (set the counter to its target directly).
*   Animations never run over data the user is trying to read twice: tables animate rows once on mount, not on every refetch.
*   The pulse ring and the sticker fly-in are scarce on purpose; do not add more.
*   Do not install `lenis`, `react-hot-toast` or `react-countup`. Smooth scrolling fights map zoom and tables, and the app already has `sonner` and `cmdk`.

## Component library

Build these in `packages/ui` before any screen. Krrish owns the base primitives; Vedant adds anything animation-specific. The Design System has live previews of Button, Chip, Sticker, KpiCard, FolderTabs and AiBadge; the rest are visible in the canvases.

| Component | Props that matter | Used by |
| :--- | :--- | :--- |
| `Button` | `variant` (primary, outline, dark), `arrow` (default on), `href` or `onClick` | every screen |
| `PillNav` | `items`, `activeId`, `cta` | page headers |
| `PageHeader` | `eyebrow` (mono code like A03), `title`, `sticker`, `script`, `actions` | every screen |
| `Card` | `lift` (default on), `tone` (surface, wine, fire, lime) | every screen |
| `KpiCard` | `label`, `value` (number), `sub`, `tone`, `pulse` | A02, O01, O03, A07 |
| `Chip` | `tone`, `dashed` | everywhere |
| `PriorityChip` | `priority` (URGENT, HIGH, NORMAL, LOW) | tables, drawers |
| `AiSuggestionChip` | `current`, `suggested`, `slaHours`; renders "agrees" or "raise to X" | A02, A03, A05 |
| `Sticker` | `children`, `size` | headers |
| `Rosette` | `label`, `size`, `spin` | AI panels, critical KPI |
| `AiPanel` | scalloped wine panel with rosette; `children`, `groundedFacts`, `degraded` | A02, A04, O05 |
| `FolderTabs` | `tabs[{id,label,count,tone}]`, `activeId`, `panelTone` | A02, A03, A10, A11 |
| `DataTable` | `columns`, `rows`, `selectable`, `onRowClick`, `row` stagger once on mount | A03, A07, A09, O02 |
| `Meter` | `value` (0–1), `tone` (lime, risk) | A05, A07, A09, O03 |
| `PairedBars` | `series[{created,resolved}]` | A02, A10, O03 |
| `HBarList` | `items[{label,value}]` | A02, A10, O01 |
| `HeatTile` | `label`, `value`, `step` (1–5) | A02, A09 |
| `Timeline` | `events[{type,time,title,note,tone}]` | A04, A05, A11 |
| `Gauge` | `value` (0–100) | A05 |
| `Ticker` | `items[]` | A01, A02, O01 |
| `Field`, `Input`, `Select`, `Textarea`, `Toggle`, `Segmented` | labelled controls, 44px minimum height | A03, A05, A06, A12, A13, O02, O06 |
| `MapFrame` | placeholder SVG now; Leaflet later; `layers`, `markers`, `hotspots` | A02, A08, A11 |
| `StateView` | `loading`, `empty`, `error`, `degraded`, `needsBackend` banners | every screen |

**Shared behaviour:**

*   Controls are real `button`, `a`, `label`, `input`. Icon-only buttons carry `aria-label`.
*   `StateView` has four looks: skeleton rows (loading), a friendly empty card with one action, an error card with the `error.code` and a retry, and a yellow banner for degraded AI or a feature that needs the backend. Use the banner wording from the mockups.
*   `DataTable` handles keyboard row selection and keeps the header sticky inside its scroll box; wide tables scroll inside their own box, never the page.

## App shells

The two apps share tokens and components but not a layout, so judges can tell the staff tool from the city view at a glance.

**Admin shell.** A 248px sidebar on the left (logo with the slow-spinning rosette, eleven nav links, a SYNTHETIC DEMO DATA sticker at the bottom) and a main column with 36px side padding. Below 900px wide the sidebar stacks above the content. The active link is lime with an ink outline and a hard shadow; hover slides the link 5px right. Badges: Case workbench shows the unassigned count (from `/analytics/overview`), Incidents shows the active count.

**Overlooker shell.** No sidebar. A top bar holds the logo, an OVERLOOKER chip, a six-link pill nav with underline ticks, and a Read only chip. Home opens with a burgundy hero band that ends in a scalloped edge; other pages open on the cream ground. Content has 40px side padding.

| Tab / Nav link | Route | Screen |
| :--- | :--- | :--- |
| Home | `/` | O01 |
| Issues | `/issues` | O02 |
| Analytics | `/analytics` | O03 |
| Community | `/community` | O04 |
| Situation | `/situation` | O05 |
| Profile | `/profile` | O06 |
| Operations | `/` | A02 |
| Case workbench | `/cases` | A03 (detail at `/cases/:id` is A04) |
| AI triage | `/cases/:id/triage` | A05 |
| Departments | `/departments` | A06 |
| Performance | `/performance` | A07 |
| City map | `/map` | A08 |
| Ward heatmap | `/wards` | A09 |
| Analytics | `/analytics` | A10 |
| Incidents | `/incidents` | A11 |
| Users | `/users` | A12 |
| Settings | `/settings` | A13 |
| Login | `/login` | A01, no shell |

**Auth and roles.** Both apps sign in through `POST /auth/login`, keep the access token in memory, refresh through `POST /auth/refresh`, and read the role from `GET /auth/me`. Route guards only hide navigation; the server decides what is allowed. A 403 shows the error card, never a blank page.

## Admin screen specs (A01–A13)

Each row says what to build and which data it reads. Endpoints are under `/api/v1`. "Gap" means the contract has no endpoint yet; build the screen against a typed adapter and show the `needsBackend` banner (section 8 lists the asks).

| Screen | Build | Data and behaviour |
| :--- | :--- | :--- |
| **A01 Login** | Split screen: wine brand panel (headline pop, three counters, ticker) and a sign-in card. Intro curtain plays once per session. | `POST /auth/login` with `identifier` and `password`, then `GET /auth/me`. Show a message per `error.code`. Demo buttons that prefill the demo accounts appear only in development. |
| **A02 Operations** | Header with pill nav, ticker, six KPI cards, AI summary panel plus map, priority queue under folder tabs, incident board, charts row. | `/analytics/overview` (KPIs, `daily_trend`), `POST /analytics/explain` (AI panel, show `warnings`), `GET /cases?sort=priority` (queue), `/analytics/incidents`, `/analytics/hotspots`, `/analytics/departments`, `/analytics/wards`. Queue shows the rules priority and the AI suggestion side by side. |
| **A03 Workbench** | Filter bar, folder-tab saved views with counts, dense table with selection, preview drawer, bulk action bar. | `GET /cases` with `q`, `status`, `category`, `priority`, `ward_id`, `department_id`, `from`, `until`, `sort`, `cursor`, `limit` (cursor pagination). Drawer reads `GET /cases/{id}`. Bulk Assign uses `/triage/decision`. Gap: escalate, merge and request information have no endpoints; hide them until they exist. |
| **A04 Case detail** | Header with chips, four stat cards, evidence grid, classification panel, work order, verification card, timeline column, notes. | `GET /cases/{id}`, `GET /cases/{id}/timeline`, `GET /evidence/{id}` for short-lived signed URLs. Actions: `POST /cases/{id}/reject` (reason required), work order, triage. Gap: internal notes. Request verification is automatic when work completes, so there is no button for it in v1. |
| **A05 AI triage** | Left: wine recommendation panel with confidence gauge and typed reasons, score bars, duplicate cards. Right: decision form and audit trail. | `POST /cases/{id}/triage/analyze` (show `reasons`, `score_breakdown`, and a `RULES ONLY` chip when `warnings` contains `RULES_ONLY`), `POST /fusion/analyze` (signals: semantic, geospatial, temporal, category), `POST /triage/decision`. A reason is required when the decision differs from the advice. |
| **A06 Departments** | Three server-state columns (Assigned, In progress, Completed), department filter, create-work-order form. No drag and drop. | `GET /work-orders?status=&limit=`, `POST /cases/{id}/work-orders`, `PATCH /work-orders/{id}`, `POST /work-orders/{id}/cancel`. The department filter runs in the browser because the endpoint filters by status only. |
| **A07 Performance** | Four highlight cards, one metrics table with SLA meters and workload bars, a caution note about comparing unequal workloads. | `/analytics/departments` (and `/{id}` for a drawer). Compute meters in the client. |
| **A08 City map** | Full-width map frame, layer buttons, filters, legend, selected-case drawer. | `GET /map/cases?bbox=` on every viewport change (never load the whole city), `/map/hotspots`, `/map/recurring-problems`. Cluster markers in the browser. Leaflet stays for now. |
| **A09 Ward heatmap** | Metric selector, ten schematic tiles coloured by heat step, ward detail panel, full ward table. | `/analytics/wards`. Tiles are schematic until the API returns ward geometry. |
| **A10 Analytics** | Three stacked folder-tab cards: Descriptive (white), Diagnostic (wine), Patterns (fire). | `/analytics/overview` (trend, categories), `/wards`, `/hotspots`, `/recurrence`, `POST /analytics/explain`. |
| **A11 Incidents** | Incident list, fire-coloured board with stats, boundary and timeline, create-incident wizard. | `GET /incidents`, `GET /incidents/{id}`, `POST /incidents` (`GeoJSON` boundary), `POST /incidents/{id}/cases`, `PATCH /incidents/{id}`. Gap: situation updates and a closing summary. |
| **A12 Users** | Role count cards, staff table with active toggles, user drawer, read-only permission matrix. | Gap: no user endpoints. Build against a `useUsers()` adapter and show the banner. Permission matrix is static, from §51A.18. |
| **A13 Settings** | Accordions: SLA classes, priority score and thresholds, AI thresholds, categories and departments, languages. | Gap: no settings endpoints. Render values from a static copy of the config files (`taxonomy.v1.json`, `triage_rules.v1.json`, `fusion_policy.v1.json`, `ai_policy.v1.json`) and show the banner. Saving needs an audited endpoint. |

## Overlooker screen specs (O01–O06)

Overlooker is read-only and city-wide. It never shows reporter identity and never offers a mutation. Where the role matrix says "aggregated", show counts, not people.

| Screen | Build | Data and behaviour |
| :--- | :--- | :--- |
| **O01 Home** | Wine hero band with a pop headline, sticker and four counters, ending in a scalloped edge; ticker; hotspot cards; fire recurring-problem card; department load bars; recent incidents. | `/analytics/overview`, `/hotspots`, `/recurrence`, `/departments`, `/incidents`. Hotspots show raw counts (recent cases against baseline), not the `ratio_vs_baseline` field, whose values are not self-explanatory. |
| **O02 Issues** | Six filters, quick-view buttons, table with List and Map toggle, "reporter identity hidden" chip. | `GET /cases` with the same filters staff use; map toggle uses `/map/cases`. Strip any reporter fields in the UI model. |
| **O03 Analytics** | Four KPI cards, 30-day paired bars, category mix, SLA by department, reopened by department. | `/analytics/overview` (`daily_trend`, `category_distribution`, `median_resolution_hours`), `/analytics/departments`. |
| **O04 Community** | Explanatory strip ("not a social feed"), three KPI cards (two dashed because they need the backend), most-backed unresolved cases, hotspot panel. | `GET /cases` sorted by `support_count` (needs a sort option, see section 8) and `/analytics/hotspots`. Total supporters and evidence volume need a new aggregate endpoint; render the dashed N/A cards until then. No names, no comments, no leaderboards. |
| **O05 Situation** | Two columns: the FACTS table (fact IDs f01 to f06, counted by the database) and the STORY panel (AI-written, wine, rosette, citations). Below it, Ask the City copilot box. | `POST /analytics/explain` returns `summary`, `highlights[{text, fact_ids}]`, `warnings`. Render fact IDs as mono chips that scroll to the matching fact row. `POST /copilot/query` currently returns `COPILOT_UNAVAILABLE` without an AI key: show the yellow degraded card with a link to Issues, plus a dashed outline of what a success looks like (answer, data, citations). |
| **O06 Profile** | Wine identity card, role capability table, language and four accessibility toggles, Save. | `GET /me`, `PATCH /me` with `preferred_language` and `accessibility: {large_text, high_contrast, reduced_motion, voice_playback}`. Apply the toggles immediately by setting data attributes on `html`; reduced motion also stops all animation. |

## API gaps and backend asks (for Parth)

Twelve things the designs need that the API does not give today. The first four block whole screens; the rest are small. Anything not built by 5 Oct ships with the `needsBackend` banner instead.

| # | Gap | Screen | Proposed endpoint or change |
| :--- | :--- | :--- | :--- |
| 1 | No user or role management | A12 | `GET /admin/users`, `PATCH /admin/users/{id}` (role, department, active), audited |
| 2 | No settings read or write | A13 | `GET/PUT /admin/settings/{section}` for taxonomy, SLA classes, triage rules, fusion and AI thresholds, audited |
| 3 | No bulk or workflow actions | A03 | `POST /cases/{id}/escalate`, `/merge`, `/request-info` |
| 4 | No internal notes | A04 | `POST /cases/{id}/notes` (staff only) |
| 5 | Work orders filter by status only | A06 | add `department_id` and `priority` params to `GET /work-orders` |
| 6 | Ward endpoint lacks category mix, resolution time, backlog, geometry | A09 | extend `/analytics/wards`; return ward boundaries as GeoJSON |
| 7 | Incidents have no updates or closing summary | A11 | `POST /incidents/{id}/updates` and a `summary` field on `PATCH` |
| 8 | No community aggregates | O04 | `GET /analytics/community` (total supporters, evidence items per period) |
| 9 | No department severity mix | A07 | add severity counts per department to `/analytics/departments` |
| 10 | Cases cannot sort by supporters | O04 | add `sort=support` to `GET /cases` |
| 11 | Department IDs are codes (`road_maintenance`), but §51A shows UUIDs | all | update the contract note; frontend treats department IDs as strings |
| 12 | `AI_GATEWAY_STORE` defaults to `demo` in code but `.env.example` says `sql` | A05, O05 | change the code default to `sql`, otherwise triage and fusion return 404 for real cases on any deploy that skips the template |

Also worth confirming: `ratio_vs_baseline` on hotspots reads 30.0 for 14 cases against a baseline of 3. If it is a rate against a different window, name it in the response, or drop it. The UI shows raw counts.

## Demo data fixes

The seeded city is realistic in shape but not in time, and judges will read these as bugs. All five are seed-script changes, not UI work. They were measured by running the real API against the seeded database on 3 Oct.

| Problem found | What it does on screen | Fix |
| :--- | :--- | :--- |
| 182 of 193 open cases show as SLA at risk; deadlines are 30 to 92 days old; department SLA rates are 0 to 33% | The KPI row and every SLA meter look broken | Generate deadlines relative to the seed's "now", with most open cases inside their window and a visible minority overdue |
| Seeded cases have no evidence and empty timelines | A04 and the case drawers are empty for every demo case | Seed placeholder photos and timeline events that match each case's status |
| The top of the priority queue repeats "Exposed live wire in W09" six times | The queue looks synthetic in the first second | Vary titles and wards across the highest-priority cases |
| No stored AI analysis, and no AI provider key | The AI column reads "rules only" with no confidence, the copilot answers `COPILOT_UNAVAILABLE` | Add a free-tier Gemini or Groq key before the demo, and seed a few stored analyses so A05 has history |
| `AI_GATEWAY_STORE` code default is `demo` | Triage and fusion 404 on real cases unless `.env` is copied | Change the default to `sql` |

Also: add one `seed_demo --reset` command that rebuilds the city and a fresh, fully worked case (like CC-2026-000006, which was created through the real API with evidence, work order and a full timeline). The 6 Oct demo should start from that reset state, not from whatever test data is in the database.

## Build order and schedule

Build what the demo shows first. The 12-scene demo flow in §59 touches four screens: a case with its supporters (A03, A04), the work order (A06), and the hotspot that shrinks after resolution (O01, O05). Those get finished and wired before anything else.

| When | Goal | Scope |
| :--- | :--- | :--- |
| Sat 3 Oct (today) | Foundation | `tokens.css`, fonts, Tailwind theme, primitives from section 4 (Button, Chip, Card, KpiCard, FolderTabs, PageHeader, StateView), both shells. Then A02 and A01 restyled on the new primitives. |
| Sun 4 Oct | Demo path, wired to the API | A03, A04, A05, A06, A11 and O01, O05. These replace mock data with real hooks. |
| Mon 5 Oct | Everything else, then polish | A07 to A10, O02 to O04, O06, plus A12 and A13 as UI-only with the banner. Motion pass, empty and error states, PPT. |
| Tue 6 Oct | Freeze | Innovibe submission. Bug fixes only, no new components. |

**Working beside Parth and Vedant (the feature dumps run in parallel):**

*   Merge `packages/ui` first. Anyone dumping features imports primitives from it; nobody restyles by hand.
*   One pull request per screen, named for its code (`feat(admin): A03 workbench`). Krrish merges design pull requests.
*   Vedant's layouts on `vedant-frontend` are already in `main`. Restyle them with the primitives; do not rebuild them.
*   If two people need the same file, the primary owner keeps it and the other posts the change they need first.
*   Never resolve a merge conflict by deleting someone else's work.
*   The Expo apps (Citizen, Field Worker) start after submission or in parallel by a different person; they reuse the tokens file and the component names, with hard shadows rebuilt as offset duplicate views.

## Acceptance checklist and Antigravity prompts

A screen is done only when every box below is ticked for it.

*   [ ] Uses only token names and `packages/ui` primitives; no raw hex, no new one-off components
*   [ ] Matches the canvas structure at 1440px, and stacks cleanly at 390px with tables scrolling inside their own box
*   [ ] Loading, empty, error and degraded states exist and use the shared `StateView` wording
*   [ ] Data comes through `packages/api-client` hooks; no numbers hard-coded in components
*   [ ] AI suggestions are dashed chips and AI text is on the wine panel; rules or human decisions are solid
*   [ ] Priority, status and heat are never colour-only; the text label is always printed
*   [ ] Keyboard: every control reachable, visible focus ring (3px lime outline), icon buttons have `aria-label`
*   [ ] Reduced motion shows the final state instantly, including counters
*   [ ] `tsc --noEmit` passes for the app (the build script runs `vite build` only, which hides type errors; the apps currently fail type checks with 10 to 24 errors each)

**Prompt 1: tokens and primitives (paste into Antigravity):**

```text
Treat /docs/CivicConnect_v2_V1_System_Design.md and
/docs/UI_IMPLEMENTATION_PLAN.md as READ-ONLY. Do not edit them. Do not invent
a parallel architecture.

Implement sections 2, 3, 4 and 5 of the UI plan only.
1. Create packages/ui/tokens.css exactly as in section 2 and import it in
apps/admin and apps/overlooker. Extend each Tailwind config from it. Load the
fonts.
2. Build the primitives in section 4 in packages/ui, one file each, with a
small example page per primitive.
3. Build the Admin shell and the Overlooker shell from section 5.
Use no raw hex, no gradients, no blur. Implement the motion table in section
3 in CSS, honouring prefers-reduced-motion. Do not touch existing pages
except to mount the shells. Run tsc --noEmit and the build. Report files
changed and anything in the plan that was ambiguous.
```

**Prompt 2: one screen at a time (replace the code):**

```text
Treat /docs/CivicConnect_v2_V1_System_Design.md and
/docs/UI_IMPLEMENTATION_PLAN.md as READ-ONLY.

Implement screen A03 (Case workbench) from section 6 of the UI plan, using
only packages/ui primitives. Match the canvas at
https://claude.ai/artifact/AuMdpribYXfKPZKsDDNqFD for structure and copy
tone. Read data through packages/api-client hooks and the endpoints listed in
the plan; do not invent endpoints or request fields. Where the plan says Gap,
build against a typed adapter and show the needsBackend banner. Add loading,
empty, error and degraded states. Do not edit other screens. Run tsc --noEmit
and report files changed, the endpoints used, and every place you had to
guess.
```
