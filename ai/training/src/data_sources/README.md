# Real-data acquisition & preparation (hybrid data strategy)

CivicConnect uses **real public data + synthetic data**, each for what it can legitimately do. Real datasets are acquired **outside git**, transformed into one canonical schema by adapters, and mapped to our taxonomy by an **explicit, versioned mapping layer**. Nothing here touches `ai/inference`.

```
external source ──download──▶ raw file (outside repo) ──profile──▶ verify columns / values / free-text / mapping coverage
                                   │
                                   └──prepare (adapter + mapping + holdout)──▶ canonical JSONL (outside repo) + PREPARE_MANIFEST
                                                                                    │
                          pairs (Chicago agency links) ──▶ real duplicate pairs ────┤
                                                                                    ▼
                                                  ai.evaluation.run_eval  --track real_holdout | hybrid | descriptive
```

## Roles: synthetic vs real

| Use **synthetic** for | Use **real public data** for |
|---|---|
| Hindi / Marathi / Hinglish / English text, code-mixing, spelling noise | realism of category demand, request volumes, spatial/temporal clustering |
| controlled edge cases, rare taxonomy classes real data lacks | evaluation on data we did not write (holdout) |
| duplicate-pair generation incl. cross-language duplicates | calibration of geo/time/category behaviour on real duplicates |
| deterministic fixtures and regression tests | cross-city / cross-country generalisation checks |
| | image-based road-issue understanding (RDD2022) |

`ai/training/src/data_sources/hybrid.py` assembles hybrid *training* sets with leakage guards: real records must be genuine citizen narratives with an exact mapped label and not in a holdout; synthetic data only augments (optional cap per real row); provenance is preserved per row. **Today no identified real dataset contains citizen narrative text**, so the guard refuses to build a hybrid text-training set from 311 data — by design.

## Indian datasets (extension) — priority order

> **Nothing below has been downloaded, opened or profiled.** The authoring sandbox cannot reach Kaggle, Mendeley, figshare or IIIT-H, so licences, column names and class names are *expectations tagged by evidence level* in the cards. Every licence is `UNVERIFIED`. Full machine-generated detail: [`TASK_MATRIX.md`](TASK_MATRIX.md) (dataset → task → allowed fields → labels → taxonomy mapping → track) and [`BMC_COLUMN_POLICY.md`](BMC_COLUMN_POLICY.md) (BMC column roles/phases per task).

| Priority | Source (`id`) | Role | Licence | Other caveats |
|---|---|---|---|---|
| **primary** | **BMC Mumbai** (`bmc_mumbai`; Kaggle competition `mumbai-nagar-seva-bmc-civic-complaint-resolution-2018-2024`) | the real Indian *structured* civic source: AI-3 routing/priority priors (descriptive), AI-5 analytics, recurrence/hotspots, taxonomy coverage, department/category mapping, realistic demos | competition rules **not read** | **origin UNVERIFIED** (real vs simulated/derived unknown); **not** an official BMC API/open-data release unless independently verified; test target withheld; no verified citizen text |
| secondary | **RDD2022** (`rdd2022`) India subset + **RDD2020** (`rdd2020`) | AI-1 image evaluation (pothole → `roads/pothole`; cracks → `roads` only) | RDD2022: README *CC BY-SA 4.0* vs external *CC BY 4.0* — unresolved. RDD2020: *CC BY-NC 3.0* reported (secondary) — **different** from RDD2022, NonCommercial | RDD2020 and RDD2022 are separate cards/mappings; never share licence assumptions |
| secondary | **BharatPotHole** (`bharatpothole`; iWatchRoad, Kaggle `surbhisaswatimohanty/bharatpothole`) | AI-1 image evaluation, dashcam frames | README (primary, fetched) states **no dataset licence**; the repo *code* is CC BY-NC-SA 4.0 and is **not** assumed to apply to the data | likely positive-only (precision not meaningful); frames from videos ⇒ must hold out whole videos |
| secondary | **Mumbai/Nashik road-surface** (`mumbai_nashik_road_surface`; Mendeley doi `10.17632/tj2m7zz4rg.2`, Data in Brief / PMC8933537) | AI-1 category-level road-surface evaluation, demo realism | not stated in any evidence seen | **identity is a CANDIDATE** — you must confirm it; the Kaggle "Indian Roads Dataset" is explicitly *not* added |
| future | **IIIT-H IDD** (`idd`) | none in V1 | unverified (variants differ) | documented only; `prepare idd` is refused |
| (optional) | NYC 311, Chicago 311 | non-Indian structured sources kept for plumbing/duplicate-pair work | unverified | see below |

### BMC Mumbai: leakage design (the part that matters)

Category, department and severity are **potential targets, not automatic input features**. Mechanisms (all tested in `tests/test_ds_bmc.py`):

1. **Column roles with phases.** Every column is assigned a role (by alias, or explicitly by `--role-map` read from the data dictionary): `identifier`/`at_submission` < `post_triage` < `post_resolution`, plus `sensitive_attribute` (complainant profile) and `pii_never_read`. Ambiguous alias matches **fail loudly** (use `--role-map`); columns no role claims are **unclassified and default-denied for every task**.
2. **Default-deny task allowlists** (`mappings/bmc_mumbai_columns.v1.json`). Each task lists its inputs, targets and forbidden roles; `TaskPolicy.validate` rejects any policy where an input is also a target, is forbidden, is later than the task's `max_phase`, or is sensitive/PII, and where an evaluation/descriptive task takes post-resolution inputs. `TaskPolicy.view` / `.read` are the only sanctioned access paths and raise `LeakageError` otherwise; all BMC evaluation functions use them.
3. **Never stored/read:** PII (names, contacts, contractors/officers) and complainant-profile columns are never read or stored; `resolution_remarks` (post-resolution free text) is never stored; citizen-satisfaction columns are not stored (task `not_pursued`, out of V1 scope). The free-text `description` is stored **only** with `--confirm-citizen-text` after you inspect it, and the intake task then audits label echo.
4. **`CaseRecord.department` is left empty.** Filling it from our taxonomy would make "category → department" a circular routing target. The source's department is kept only as `source_agency`.
5. **Leakage audits** run at prepare time and via `cli leakage-audit`: target determinism (a target ≥ 99% determined by its allowed inputs ⇒ the evaluation is *blocked* as vacuous — the invented fixture's severity/department trip this on purpose), split straddle / spatiotemporal twins, text-echo rate, censoring (unresolved complaints are right-censored, never silently dropped), and `views_clean`.
6. **Claims.** Origin-unverified data can never support a real-world claim (`claims_for` blocks `real_holdout`/hybrid real-slice claims; descriptive banners say "ORIGIN UNVERIFIED"). BMC tasks run on the `descriptive` track only.

| BMC task | status | inputs (summary) | target | phase limit |
|---|---|---|---|---|
| `taxonomy_coverage` | supported | source category/subcategory | — | at submission |
| `routing_agreement` | conditional | category, ward | source department (mapped by a DRAFT keyword table) | at submission |
| `triage_priority_prior` | conditional | category, ward, location, time, channel | severity, priority (distributions only) | at submission |
| `resolution_time_prior` | conditional | + severity/priority/department/SLA target | resolution hours (resolved only; censoring reported) | post-triage |
| `recurrence_hotspot` | supported | time, ward, location, category | — | at submission |
| `intake_text` | conditional | description (**operator-confirmed citizen text**) | category | at submission; `source_category` forbidden as input |
| `fusion_pairs` | conditional | time, place, category | duplicate flag | requires duplicate/parent columns |
| `demo_seed` | demo only | wide, incl. outcomes | — | demo only; never evaluated |
| `citizen_satisfaction` | not pursued | — | — | out of V1 scope |

### Indian road-image sources: what is guarded

* One generic adapter (`adapters/detection.py`) for BharatPotHole and Mumbai/Nashik; RDD2020 reuses the RDD adapter (ids prefixed `rdd2020:`).
* **Annotation format is never guessed**: pass `--format {voc,yolo,coco,folder}` after `cli profile-images <root> --out …` (which reports facts and *candidate* formats only). YOLO needs the dataset's own class-names file (`--class-names-file`); unknown class ids are counted, never mapped.
* **Frames from one video are near-duplicates**: group ids come from an explicit rule (`--group-by dir|regex|block|none`), holdouts (`--holdout-fraction`) keep whole groups together and are *refused* with `--group-by none`; the manifest reports straddling groups (must be 0). RDD index-blocks serve the same purpose.
* **No invented taxonomy**: only an exact pothole class maps to `roads/pothole`; generic damage → `roads`; cracks, speed breakers, barriers, paved/unpaved/season/water scenes are `out_of_scope`/unmapped. Videos must be converted to frames externally.
* Positive-only datasets get a manifest warning, and vision evaluation sets `pothole_precision_valid=false` when (almost) every image is a pothole.

**Still not available anywhere here:** real Hindi/Marathi/Hinglish citizen narratives (BMC's text, if any, is unverified), real before/after resolution evidence (AI-4 tested with scripted fixtures only; a *synthetic* before/after set is not generated yet — listed as a GAP in the task matrix), severity ground truth.

## Datasets investigated before the Indian extension (details in `cards/*.json`)

| Source | Version / access | Licence status (**read this**) | Subset (to be chosen) | Intended use |
|---|---|---|---|---|
| **NYC 311** (`erm2-nwe9`) | rolling; Socrata API/CSV | NYC Open Data Terms of Use — **UNVERIFIED** (only a web-search summary was seen; official page unreachable from the dev sandbox) | bounded date window, mapped complaint types | analytics validation, calibration inputs, taxonomy-coverage, demo |
| **Chicago 311** (`v6vf-nfxy`) | rolling; Socrata API/CSV | City of Chicago terms — **UNVERIFIED**; duplicate/parent column names **unconfirmed** | bounded window; rows with duplicate/parent fields | **real duplicate pairs (AI-2)**, analytics validation, SLA priors |
| **RDD2022** (figshare 21431547) | PASCAL VOC, 6 countries, 47k images (secondary), test images unannotated | **UNRESOLVED CONFLICT**: project README says **CC BY-SA 4.0**, search summaries of figshare/journal say **CC BY 4.0** → treat as the stricter share-alike until checked at figshare (`cli figshare-license` prints figshare's own licence field) | India first + one other country; classes D00/D10/D20/D40; train split only | image-modality evaluation (AI-1), optional detector fine-tuning |

Evidence discipline: each card entry is tagged `primary` / `secondary` / `recalled`; a licence can only be `VERIFIED_PRIMARY` with primary evidence (enforced by the schema). Required citations for RDD2022 (dataset article + CRDDC'2022 summary + review) are in its card. **Do not publish results from any source whose licence is unverified.**

## What each dataset can — and cannot — support

| | AI-1 text | AI-1 image | AI-2 fusion | AI-3 triage | AI-4 resolution | AI-5 analytics | AI-6 copilot |
|---|---|---|---|---|---|---|---|
| **NYC 311** | ✗ no narrative text¹ | ✗ | ◐ distributions only (no duplicate labels) | ◐ resolution-time priors; **no** severity | ✗ | ✔ validate hotspot/recurrence/baseline logic | ◐ demo realism only |
| **Chicago 311** | ✗ no narrative text¹ | ✗ | ✔ **real agency-linked duplicates** for geo/time/category signals² | ◐ resolution-time priors; no severity | ✗ | ✔ | ◐ demo realism only |
| **RDD2022** | ✗ | ✔ road damage only (D40→`roads/pothole`; cracks→`roads`, no subcategory in taxonomy v1) | ✗ no duplicate pairs | ✗ no severity | ✗ no before/after | ✗ | ✗ |
| **Synthetic** | ✔ multilingual coverage | ✗ | ✔ controlled pairs | ✗ circular | ✗ | ✗ | ✗ |

¹ Public columns are agency category/descriptor fields (to be confirmed with `cli profile`). Scoring a classifier on text derived from the category it must predict is **label leakage**; the adapters emit no text by default, and `--include-category-text` tags it `source_category_text`, which every evaluation track refuses.
² No semantic signal (no text); negatives are sampled and may include unlinked real duplicates (precision is a conservative bound); single city.

**Gaps no identified dataset fills:** real Hindi/Marathi/Hinglish citizen narratives, real before/after resolution evidence, severity ground truth, Indian-municipality categories/SLAs. These need partner data (with consent/licensing) — not invented here.

## Architecture (files)

| File | Role |
|---|---|
| `cards/*.json`, `card_schema.py` | per-dataset provenance/licence/attribution/subset/intended-use/capabilities; **terms gate** (`--accept-terms <id>`, `--acknowledge-unverified-license`) |
| `canonical.py` | `CaseRecord`, `ImageRecord`, `PairRecord`, `Provenance` (kind, source, version, record id, licence + verified flag, label origin, mapping id/version). `text_origin` separates citizen narrative from category text |
| `mapping.py`, `mappings/*.v1.json` | explicit first-match-wins rules → taxonomy category/subcategory, or `out_of_scope` / `unmapped`; `CoverageReport`. **All tables are DRAFT** (NYC/Chicago rules written without access to the live files; RDD classes from the project README) |
| `columns.py` | alias-based header resolution (fails loudly with the real headers), tolerant readers (csv/jsonl/json/gz), parsers, deterministic reservoir sampling |
| `adapters/` | `nyc311`, `chicago311` (tabular), `rdd2022` (PASCAL VOC → image references + boxes; also serves `rdd2020`), `bmc_mumbai` (role-policy-driven), `detection` (VOC/YOLO/COCO/folder, group ids), `synthetic`. Address columns are never read |
| `column_roles.py`, `mappings/bmc_mumbai_columns.v1.json` | column-role policy: phases, default-deny per-task allowlists, `LeakageError`, header classification with `--role-map` |
| `leakage.py` | target determinism, split/spatiotemporal straddle, text echo, censoring, view cleanliness |
| `image_profile.py` | `profile-images`: facts + candidate formats for an external image tree |
| `task_matrix.py`, `TASK_MATRIX.md`, `BMC_COLUMN_POLICY.md`, `task_matrix.v1.json` | generated dataset→task→fields→labels→mapping→track manifest (a test fails if it drifts) |
| `download/` | `socrata.py` (bounded, paged, auditable `RETRIEVAL.json`, no token written), `figshare.py` (list/licence/size-guarded download with md5) — external dirs only |
| `profile.py` | pre-flight: columns, value space, free-text candidates, date/coordinate coverage, draft mapping coverage |
| `splits.py` | time / group (country, district) / spatial-cell holdouts so near-identical rows cannot straddle train and test |
| `pairs.py` | real duplicate pairs from agency parent links + sampled unlinked negatives |
| `hybrid.py` | leakage-guarded real+synthetic training-set assembly |
| `paths.py` | **output guard**: only outside the repo or `ai/artifacts/real_data/` (gitignored); everything else is refused |
| `cli.py` | `cards`, `card`, `download`, `figshare-*`, `profile` (incl. `bmc_mumbai`), `profile-images`, `prepare` (incl. Indian sources), `leakage-audit`, `matrix`, `pairs` |

Git hygiene is enforced, not just documented: `ai/.gitignore` ignores `artifacts/real_data/**` (even whitelisted filenames), the CLI refuses unsafe output paths, and `test_no_real_or_large_data_is_tracked_in_git` fails on tracked real-data/large files. Tests use only tiny **invented format fixtures** (`tests/fixtures/real_data_formats/`, IDs `FMT-*`, labelled NOT REAL).

## Evaluation tracks (`ai/evaluation/provenance.py`, `run_eval.py`)

| Track | Data | May claim… | Command sketch |
|---|---|---|---|
| `synthetic` (default) | synthetic only | **never** real-world accuracy | `run_eval --task intake|fusion …` |
| `real_holdout` | real only, **holdout rows only** | a *scoped* real claim only if n ≥ 200, licence verified, and conditions in the report hold ("agreement with `<source>` labels via draft mapping X on holdout; city-specific; not ground truth") | `run_eval --task fusion --track real_holdout --real-data pairs.jsonl` |
| `hybrid` | both | **no pooled number**: synthetic and real slices reported separately | `run_eval --task fusion --track hybrid --real-data pairs.jsonl` |
| `descriptive` | real only | no model claim (e.g. taxonomy coverage: how real demand lands in taxonomy v1, which labels have **no real examples**) | `run_eval --task taxonomy_coverage --real-data records.jsonl` |

Every report carries `track`, a `provenance` table (source, kind, n, licence + verified?, label origin, text origin, mapping version), a `claims` block and a banner. Guards: synthetic track rejects real rows; real track rejects synthetic rows and **any row not in a holdout**; real intake evaluation refuses rows without genuine narrative text; unlabeled rows are rejected outright; vision evaluation needs a configured provider and marks runs INVALID if the provider degraded on >10% of images.

## Workflow (when datasets are chosen)

1. `cli card <id>` → read the terms; **verify the licence at the primary source**, then update the card (`status: VERIFIED_PRIMARY` + primary evidence) — for RDD2022 start with `cli figshare-license`.
2. Download a **bounded** slice outside the repo (`cli download …` or attach a Kaggle Dataset); notebook `04_real_data_prepare_evaluate_kaggle.ipynb` wraps steps 2–6.
3. `cli profile …` → confirm real column names, the real label space, whether any column is genuine narrative text; **extend/correct the mapping table**; bump its version.
4. `cli prepare … --holdout-after DATE` (311) or `--holdout-countries …` (RDD2022).
5. `cli pairs …` (Chicago, if duplicate/parent columns exist).
6. `run_eval` on the appropriate track; optionally re-fit fusion weights on real pairs: `train_fusion_calibrator --kind real --pairs-train … --pairs-val …` (status `calibrated_real`, provenance recorded).
7. Only then decide which numbers (if any) may appear in claims, with their provenance.

### BMC Mumbai workflow
1. Read the competition **Rules** and data description (is it real BMC data, simulated, or derived? any licence/redistribution limits?). Update the card (`licence`, `origin_status`) only with primary evidence.
2. Download via Kaggle yourself (terms accepted in your account) to a directory **outside the repo** (or `ai/artifacts/real_data/`).
3. `python -m ai.training.src.data_sources.cli profile bmc_mumbai --input train.csv --out …/bmc_profile.json` — lists resolved roles, unclassified/PII/sensitive columns, determinism purity, mapping coverage, free-text candidates, runnable tasks.
4. Read the data dictionary; write `role_map.json` (`{"<column>": "<role>"}`) for anything ambiguous or unclassified; extend `bmc_mumbai_to_civic.v1.json` for unmapped categories; bump versions.
5. `cli prepare bmc_mumbai --input … --out … --role-map role_map.json --accept-terms bmc_mumbai --acknowledge-unverified-license [--holdout-after DATE] [--confirm-citizen-text] [--resolution-unit hours|days]`.
6. `cli leakage-audit --records …/records.jsonl`; `run_eval --task resolution_time_prior|recurrence_hotspot|routing_agreement|triage_priority_prior|taxonomy_coverage --real-data …/records.jsonl` (descriptive).

### Indian image workflow
`cli profile-images <root> --out …` → choose `--format` yourself → (YOLO) supply `--class-names-file` → choose a group rule → `cli prepare bharatpothole|mumbai_nashik_road_surface|rdd2020|rdd2022 …` → `run_eval --task vision --track real_holdout --real-data … --image-root <root>` (needs a configured provider).

## Not verified / blocked in the authoring environment
* Official pages for NYC 311, Chicago 311 and figshare were **unreachable** (egress proxy). Their licence/column/format details above come from web-search summaries or are expectations, tagged as such in the cards.
* No real data was downloaded or used; all adapter/evaluation tests run on invented format fixtures.
* Mapping tables are hypotheses until validated with `profile` on the real files. BMC column names, class names for BharatPotHole / Mumbai-Nashik, and the BMC category list (user-reported) are **expectations**, not read from the files.
* Kaggle, Mendeley, figshare and IIIT-H were unreachable; BharatPotHole's repository README (GitHub) was the only primary source fetched for the Indian datasets.
