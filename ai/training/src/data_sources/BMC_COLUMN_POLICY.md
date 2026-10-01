# BMC Mumbai column policy (default-deny)

> GENERATED from `mappings/bmc_mumbai_columns.v1.json`. Column NAMES are expectations: the Kaggle page/data dictionary were unreachable. Roles are assigned by alias or by an explicit `--role-map`; every column no role claims is **unclassified and unavailable to every task**. Not an official BMC source; origin and licence unverified.

## Roles and phases

| role | phase | stored in prepared output | note |
|---|---|---|---|
| `complaint_id` | identifier | yes | row identifier |
| `created_at` | at_submission | yes | when the complaint was filed (confirm in the data dictionary) |
| `ward` | at_submission | yes | BMC administrative ward (location context) |
| `latitude` | at_submission | yes |  |
| `longitude` | at_submission | yes |  |
| `locality` | at_submission | yes | coarse locality (NOT a street address) |
| `source_category` | at_submission | yes | raw complaint category: the LABEL source for intake — never an input to intake |
| `source_subcategory` | at_submission | yes |  |
| `category` | at_submission | yes | taxonomy category mapped from source_category by an explicit mapping |
| `subcategory` | at_submission | yes | taxonomy subcategory (exact mappings only) |
| `filing_channel` | at_submission | yes | how the complaint was filed |
| `description` | at_submission | yes | free text; used ONLY after the operator confirms it is citizen-written, and never when it echoes the label |
| `infrastructure_context` | at_submission | yes | REVIEW before use: could contain post-event information |
| `department` | post_triage | yes | department the complaint was routed to (routing TARGET; derived after triage) |
| `severity` | post_triage | yes | severity as recorded: provenance unknown; a triage TARGET only after a determinism check |
| `priority` | post_triage | yes | priority as recorded; triage TARGET |
| `sla_target_hours` | post_triage | yes | SLA assigned at triage (unit to be confirmed) |
| `assigned_contractor` | post_triage | yes | contractor assigned to the work order: not known at triage time |
| `duplicate_flag` | post_triage | yes | duplicate label assigned by the process (fusion TARGET) |
| `parent_complaint_id` | post_triage | yes |  |
| `status` | post_resolution | yes | workflow outcome |
| `closed_at` | post_resolution | yes |  |
| `resolution_duration` | post_resolution | NO | unit unknown: converted only with an explicit --resolution-unit |
| `resolution_hours` | post_resolution | yes | computed duration in hours (closed_at - created_at, or resolution_duration with explicit unit); a TARGET only |
| `resolution_remarks` | post_resolution | NO | free text written after the work: never stored, never an input |
| `reassigned` | post_resolution | yes | reassignment during resolution |
| `escalated` | post_resolution | yes | escalation during resolution |
| `sla_breached` | post_resolution | yes | derived outcome |
| `reopened` | post_resolution | yes |  |
| `citizen_rating` | post_resolution | NO | post-resolution feedback |
| `citizen_satisfied` | post_resolution | NO | the Kaggle competition target; a post-resolution outcome, out of V1 scope |
| `complainant_profile` | sensitive_attribute | NO | complainant attributes: protected/sensitive (system design §13) |
| `pii` | pii_never_read | NO | direct identifiers |

Phases: `identifier`/`at_submission` (known when filed) < `post_triage` (assigned after triage) < `post_resolution` (outcomes/events after work starts). `sensitive_attribute` and `pii_never_read` roles are never read, stored, input or target.

## Per-task permissions

### `taxonomy_coverage` — supported (AI-3/AI-5; track `descriptive`; max input phase `at_submission`)

- **allowed inputs:** `source_category`, `source_subcategory`, `category`, `subcategory`
- **targets:** —
- **forbidden (explicit):** `phase:post_triage`, `phase:post_resolution` (+ all sensitive/PII roles)
- **requires:** —
- **leakage checks:** —
- How the real complaint label space lands in taxonomy v1 (and which taxonomy labels have no real examples).

### `routing_agreement` — conditional (AI-3; track `descriptive`; max input phase `at_submission`)

- **allowed inputs:** `source_category`, `source_subcategory`, `category`, `subcategory`, `ward`
- **targets:** `department`
- **forbidden (explicit):** `severity`, `priority`, `sla_target_hours`, `assigned_contractor`, `phase:post_resolution` (+ all sensitive/PII roles)
- **requires:** `department`, `source_category`
- **leakage checks:** `target_determinism`
- condition: report the purity of department given source_category; if >= 0.99 the agreement is vacuous
- Agreement between BMC's recorded department (mapped to ours) and our category->department routing. NOT model accuracy.

### `triage_priority_prior` — conditional (AI-3; track `descriptive`; max input phase `at_submission`)

- **allowed inputs:** `category`, `subcategory`, `ward`, `latitude`, `longitude`, `created_at`, `filing_channel`
- **targets:** `severity`, `priority`
- **forbidden (explicit):** `department`, `assigned_contractor`, `sla_target_hours`, `phase:post_resolution` (+ all sensitive/PII roles)
- **requires:** `severity`, `priority`
- **leakage checks:** `target_determinism`
- condition: severity/priority provenance unknown: a determinism check against category is mandatory
- condition: descriptive priors only: no learned triage model is trained on this data
- Distribution of recorded severity/priority by category/ward/time; informs priority-score sanity checks, never ground truth.

### `resolution_time_prior` — conditional (AI-3/AI-5; track `descriptive`; max input phase `post_triage`)

- **allowed inputs:** `category`, `subcategory`, `ward`, `latitude`, `longitude`, `created_at`, `filing_channel`, `severity`, `priority`, `department`, `sla_target_hours`
- **targets:** `resolution_hours`
- **forbidden (explicit):** `assigned_contractor`, `status`, `closed_at`, `resolution_remarks`, `reassigned`, `escalated`, `sla_breached`, `reopened`, `citizen_rating`, `citizen_satisfied` (+ all sensitive/PII roles)
- **requires:** `closed_at`, `resolution_duration`
- **leakage checks:** `censoring_reported`
- condition: triage-time information (severity, priority, department, SLA) is legitimately known before resolution
- condition: unresolved complaints are right-censored: report the censored share, never silently drop them
- Resolution-duration distributions per category/ward to sanity-check SLA hours.

### `recurrence_hotspot` — supported (AI-5; track `descriptive`; max input phase `at_submission`)

- **allowed inputs:** `created_at`, `ward`, `latitude`, `longitude`, `category`, `subcategory`
- **targets:** —
- **forbidden (explicit):** `phase:post_triage`, `phase:post_resolution` (+ all sensitive/PII roles)
- **requires:** —
- **leakage checks:** `split_straddle`
- Validate deterministic recurrence/hotspot definitions (design §38-39) on realistic Indian ward-level data.

### `intake_text` — conditional (AI-1; track `real_holdout`; max input phase `at_submission`)

- **allowed inputs:** `description`, `ward`, `latitude`, `longitude`, `filing_channel`
- **targets:** `category`, `subcategory`
- **forbidden (explicit):** `source_category`, `source_subcategory`, `department`, `severity`, `priority`, `phase:post_triage`, `phase:post_resolution` (+ all sensitive/PII roles)
- **requires:** `description`, `source_category`; operator confirms `description_is_citizen_text`
- **leakage checks:** `text_contains_label_rate`, `split_straddle`
- condition: the operator must inspect samples and confirm the column is citizen-written free text
- condition: source_category (the label) must not be an input
- condition: a description that echoes the label is refused
- Only possible if a genuine citizen description column exists. No such column is known; nothing here claims it does.

### `fusion_pairs` — conditional (AI-2; track `real_holdout`; max input phase `at_submission`)

- **allowed inputs:** `created_at`, `ward`, `latitude`, `longitude`, `category`, `subcategory`
- **targets:** `duplicate_flag`
- **forbidden (explicit):** `parent_complaint_id`, `phase:post_resolution` (+ all sensitive/PII roles)
- **requires:** `duplicate_flag`, `parent_complaint_id`
- **leakage checks:** `split_straddle`
- Possible only if the file carries duplicate/parent information; none is known.

### `demo_seed` — demo_only (AI-6; track `none`; max input phase `post_resolution`)

- **allowed inputs:** `source_category`, `category`, `subcategory`, `ward`, `latitude`, `longitude`, `created_at`, `filing_channel`, `locality`, `department`, `severity`, `priority`, `status`, `closed_at`, `resolution_hours`
- **targets:** —
- **forbidden (explicit):** — (+ all sensitive/PII roles)
- **requires:** —
- **leakage checks:** —
- Realistic rows for copilot/demo databases; labelled as unverified-origin data; never an evaluation; sensitive/PII roles excluded.

### `citizen_satisfaction` — not_pursued (—; track `none`; max input phase `at_submission`)

- **allowed inputs:** —
- **targets:** —
- **forbidden (explicit):** — (+ all sensitive/PII roles)
- **requires:** —
- **leakage checks:** —
- The competition target is a post-resolution outcome. CivicConnect V1 has no satisfaction/reputation scoring; the column is never an input to any task.
