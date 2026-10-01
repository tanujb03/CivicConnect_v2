# CivicConnect V1 civic taxonomy (`taxonomy.v1.json`)

> ## ⚠ DRAFT — requires **Tanuj + Parth** review before Parth seeds the database
>
> `status` in the JSON is `DRAFT_REQUIRES_REVIEW` and `approved_by` is empty. Do **not** seed `Department`, category or SLA tables from this file until both reviewers have signed off
> (set `status` to `APPROVED`, fill `review.approved_by`, bump nothing else). Once seeded, IDs are permanent: never rename or reuse an ID; add new IDs and bump `taxonomy_version`.

- Version: `1.0.0-draft` · 27 subcategories · 9 categories (incl. `other`) · 8 departments (matches the 8 in system design §58)
- Scope: practical hackathon-demo taxonomy, **not** a government-wide classification. It is a V1 *implementation artifact*; the frozen design document is unchanged.
- Consumed by: AI intake (provider enums + local classifier labels), triage rules, fusion gating, copilot tool validation. Admin-editable in V1 per A13 (categories/departments/SLA are configurable), with this file as the seed/default.

## 1 · Naming conventions (and how the inconsistencies were resolved)

| Kind | Convention | Examples | Why |
|---|---|---|---|
| category, subcategory, department **id** | lowercase `snake_case`, stable machine ID | `roads`, `pothole`, `road_maintenance` | matches the §11 intake example (`"category": "roads"`, `"suggested_department": "road_maintenance"`) |
| severity, priority, SLA class | `UPPER_SNAKE_CASE` enum | `HIGH`, `URGENT`, `EMERGENCY` | matches §51A (`LOW\|MEDIUM\|HIGH\|CRITICAL`, `NORMAL`, `URGENT`) |
| department `code` | short uppercase alias | `WATER`, `ROADS` | resolves the §51A.8 example (`"department": "WATER"`); accepted as an *input alias*, never emitted |
| labels | `{en, hi, mr}` strings | `Pothole` / `गड्ढा` / `खड्डा` | UI text only; **Hindi/Marathi labels need native-speaker review** |

**Resolved inconsistencies**

1. §11 used lowercase IDs while §51A.8 showed `WATER` → one canonical lowercase ID per entity; uppercase `code` kept as an alias (`Taxonomy.resolve_department("WATER") == "water_supply"`).
2. §51A shows priorities `NORMAL` (case creation) and `URGENT` (triage) but no full list → `LOW < NORMAL < HIGH < URGENT`.
3. §51A.8 shows `sla_hours: 24` for `URGENT` → the `URGENT` SLA class is 24 h; a further `EMERGENCY` class (4 h) is reserved for `CRITICAL` severity.
4. A category and its department may share an ID (`water_supply`, `drainage_sewerage`, `street_lighting`). They live in separate API fields and are unique *within* each namespace; subcategory IDs never collide with either.

> **Decision needed (Parth / API owners):** the AI layer emits the canonical department ID (e.g. `water_supply`) in `triage.recommendation.department` and `proposal.suggested_department`. The §51A.8 example shows the literal `"WATER"`. If the contract is meant to carry the *code*, it is a one-line change in the adapter — tell us which before the generated API client is frozen.

## 2 · Hierarchy

`category → department` is 1:1 (except `other`, which has **no** department and therefore always needs human routing). A subcategory may override its category's department (`department_id` field; none do in V1).

| Category | Department (code) | Subcategory | Base severity | Safety-critical |
|---|---|---|---|---|
| **`roads`**<br>Roads & Footpaths | `road_maintenance` (ROADS) | `pothole` — Pothole | MEDIUM |  |
|  |  | `road_cave_in` — Road cave-in / sinkhole | HIGH | yes |
|  |  | `damaged_footpath` — Damaged footpath | LOW |  |
| **`water_supply`**<br>Water Supply | `water_supply` (WATER) | `pipe_leakage` — Pipe leakage | MEDIUM |  |
|  |  | `no_water_supply` — No water supply | HIGH |  |
|  |  | `contaminated_water` — Contaminated water | HIGH | yes |
|  |  | `low_water_pressure` — Low water pressure | LOW |  |
| **`sanitation`**<br>Sanitation & Waste | `solid_waste` (SWM) | `garbage_overflow` — Overflowing garbage | MEDIUM |  |
|  |  | `missed_garbage_collection` — Missed garbage collection | LOW |  |
|  |  | `illegal_dumping` — Illegal dumping | MEDIUM |  |
|  |  | `dead_animal` — Dead animal | MEDIUM |  |
| **`drainage_sewerage`**<br>Drainage & Sewerage | `drainage_sewerage` (DRAINAGE) | `blocked_drain` — Blocked drain | MEDIUM |  |
|  |  | `sewage_overflow` — Sewage overflow | HIGH |  |
|  |  | `missing_manhole_cover` — Missing manhole cover | HIGH | yes |
| **`street_lighting`**<br>Street Lighting | `street_lighting` (LIGHTING) | `light_not_working` — Streetlight not working | LOW |  |
|  |  | `flickering_light` — Flickering streetlight | LOW |  |
|  |  | `exposed_live_wire` — Exposed live wire | CRITICAL | yes |
| **`parks_trees`**<br>Parks & Trees | `parks_horticulture` (PARKS) | `fallen_tree` — Fallen tree / branch | HIGH | yes |
|  |  | `overgrown_vegetation` — Overgrown vegetation | LOW |  |
|  |  | `damaged_park_equipment` — Damaged park equipment | MEDIUM |  |
| **`public_health`**<br>Public Health | `public_health` (HEALTH) | `mosquito_breeding` — Mosquito breeding / stagnant water | MEDIUM |  |
|  |  | `stray_animals` — Stray animal menace | MEDIUM |  |
|  |  | `open_burning` — Open burning | MEDIUM |  |
| **`traffic_encroachment`**<br>Traffic & Encroachment | `traffic_enforcement` (TRAFFIC) | `illegal_parking` — Illegal parking | LOW |  |
|  |  | `footpath_encroachment` — Footpath encroachment | LOW |  |
|  |  | `signal_not_working` — Traffic signal not working | HIGH | yes |
| **`other`**<br>Other / Unclear | — (human routing) | `unclassified` — Unclassified | LOW |  |

Base severity is the *deterministic baseline*; keyword escalators in `triage_rules.v1.json` (school/children, hospital, injury/accident/electric shock; English, Hindi, Marathi, Hinglish) bump it by one level (max `CRITICAL`). Safety-critical subcategories can never be lowered by AI.

## 3 · Severity → priority → SLA

| Severity | Rank | Score points | | Priority | Rank | Default SLA class |
|---|---|---|---|---|---|---|
| LOW | 1 | 10 | | LOW | 1 | ROUTINE |
| MEDIUM | 2 | 30 | | NORMAL | 2 | STANDARD |
| HIGH | 3 | 55 | | HIGH | 3 | EXPEDITED |
| CRITICAL | 4 | 80 | | URGENT | 4 | URGENT |

| SLA class | Hours |
|---|---|
| EMERGENCY | 4 |
| URGENT | 24 |
| EXPEDITED | 48 |
| STANDARD | 72 |
| ROUTINE | 168 |

Priority is **not** an AI output (§36). `priority_score = severity points + support (+2 each, cap 10) + sensitive location (+10 each, cap 15) + case age (+1/day, cap 10) + recurrence (+5 each, cap 10) + incident (+10) + SLA-risk (+10 once ≥75% of the SLA has elapsed)`, capped at 100. Thresholds: ≥80 `URGENT`, ≥55 `HIGH`, ≥30 `NORMAL`, else `LOW`. `CRITICAL` severity is always `URGENT` with the `EMERGENCY` (4 h) SLA. All numbers live in `triage_rules.v1.json` (configuration, admin-overridable). The §51A.8 example (HIGH, URGENT, 24 h) is reproducible: HIGH + 5 supporters + school + 1 recurrence = 80.

## 4 · Guidance for seeding (Parth)

- Use the IDs as natural/unique keys (`categories.id`, `subcategories.id`, `departments.id`); store `taxonomy_version` with seeded rows and on `AIAnalysis` records (the AI adapter returns it in `ai_metadata.taxonomy_version`).
- `AIAnalysis.result_json` stores IDs, never labels. Render labels from the table in the user's language.
- The intake/triage code accepts only IDs from this file; unknown IDs from a model are repaired or rejected, so DB changes must be mirrored here (or the adapter pointed at a DB-backed taxonomy — future work).
- `other/unclassified` has no department: route such cases to `NEEDS_REVIEW` (§35) for a human to categorise.

## 5 · Open review questions

1. Are the 8 departments and the category→department mapping right for the demo city? (e.g. `dead_animal` under solid waste vs public health; `missing_manhole_cover` under drainage vs roads.)
2. SLA hours (4 / 24 / 48 / 72 / 168) and the priority thresholds are plausible defaults, **not** validated against any municipality's real SLAs.
3. Base severities and the safety-critical flags (`road_cave_in`, `contaminated_water`, `missing_manhole_cover`, `exposed_live_wire`, `fallen_tree`, `signal_not_working`).
4. Hindi and Marathi labels and keyword escalators — need a native-speaker pass.
5. Should citizens ever see `other`? V1 assumes the citizen confirms/edits the proposal and the admin recategorises.

## 6 · Where it is used

`ai/inference/config.py` (loader + validation, `Taxonomy`), `ai/inference/prompts.py` (provider JSON-schema enums), `ai/inference/triage/rules.py`, `ai/inference/fusion/` (category gate), `ai/inference/copilot/` (tool argument validation), local classifier label set (`manifest.json → label_ids`). Integrity is enforced by `ai/inference/tests/test_taxonomy.py`.
