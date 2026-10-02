# Demo city v1 — SYNTHETIC (system design §58)

> **Every record is synthetic and labelled so.** Wards, users, cases, reports, incidents and every number are invented to make the Admin and Overlooker dashboards, fusion, triage, copilot and analytics demonstrable. Nothing describes a real city, citizen or municipal performance. Hindi/Marathi/Hinglish text comes from the project's template generator and is not reviewed by native speakers.

Regenerate / verify: `python -m ai.training.src.build_demo_city --out ai/evaluation/datasets/demo_city_v1 [--check]` (seed `20261001`, deterministic). Evaluate: `python -m ai.evaluation.eval_demo_city --artifact ai/artifacts/civic_text_b0/<version>`.

| File | Entity (§34) | Rows | Notes |
|---|---|---|---|
| `wards.jsonl` | Ward | 10 | GeoJSON boundary + centroid; labels `W01`–`W10` |
| `departments.jsonl` | Department | 8 | from `taxonomy.v1.json` (ids are the taxonomy's department ids) |
| `users.jsonl` | User | 96 | citizens (4 preferred languages), operators, managers, ward officers, field workers, admin, overlooker. **No contact data, no credentials** — Parth creates logins for the demo roles |
| `cases.jsonl` | CivicCase | 560 | `public_case_id` `DEMO-2026-…`; category/subcategory/severity/priority/SLA/department/ward/location/status/timestamps; `scenario` says why a case exists |
| `report_signals.jsonl` | ReportSignal | 614 | original text + language + source type; `text_split_pool` (`train`/`val`/`test`) tells which template family pool the text came from |
| `case_relations.jsonl` | CaseRelation | 27 | `POSSIBLE_DUPLICATE` between separate cases |
| `status_events.jsonl` | timeline | ~5.6k | every transition follows the §35 state machine |
| `work_orders.jsonl`, `verifications.jsonl` | WorkOrder, Verification | ~540 | derived from the lifecycles |
| `incidents.jsonl` | Incident | 5 (3 active) | polygon geometry |
| `ground_truth.json` | — | — | planted duplicate groups, recurring sites, hotspots, incident cases |
| `manifest.json` | — | — | seed, counts, sha256 of every file, ground-truth recovery |

**§58 minimums met:** 10 wards · 8 departments · 560 cases · 8 categories · 25 merged duplicate groups + 26 possible-duplicate pairs · 12 planted recurring sites (4–6 cases within 150 m / 8 months, ≥ 2 resolved, ≥ 1 reopened) · 3 emerging hotspots · ~190 SLA breaches · ~360 resolved · 45 reopened (14 currently `REOPENED`) · 3 active incidents.

## Honest limits
* Priority/SLA/severity come from the deterministic §36 rules, not a model. Lifecycle durations, backlog and reopen rates are invented.
* No images or audio: AI-4 before/after evidence is **not** represented anywhere in this dataset.
* Text is template-family text. Classifier results on it are held-out **only** for `text_split_pool == test`.
* Location tags (school/hospital/market/transit) come from fictional named places.
* A few clusters exist because the planted hotspots/incidents are themselves dense; `ground_truth.json` marks them, and the validator checks that no recurring site is unexplained.
