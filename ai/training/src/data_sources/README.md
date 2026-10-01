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

> **Nothing below has been downloaded, opened or profiled by this tooling**, and nothing is ever copied to a laptop or into git: the datasets are processed **in place on Kaggle** (`/kaggle/input/...`, see *Kaggle workflow* below). The authoring sandbox cannot reach Kaggle, Mendeley, figshare or IIIT-H, so licences, column names and class names are *expectations tagged by evidence level* in the cards. Every licence is `UNVERIFIED`. Machine-generated detail: [`TASK_MATRIX.md`](TASK_MATRIX.md) (dataset → task → allowed fields → labels → taxonomy mapping → track) and [`BMC_COLUMN_POLICY.md`](BMC_COLUMN_POLICY.md).

| Priority | Source (`id`) | Evidence class | Role | Licence | Caveats |
|---|---|---|---|---|---|
| **priority (real)** | **Mumbai/Nashik road surface** (`mumbai_nashik_road_surface`; Mendeley `tj2m7zz4rg`) | real | AI-1 category-level image evaluation (potholes only where explicitly labelled), Maharashtra visual grounding, demo realism | **CC BY 4.0 reported by the repo owner** from the Mendeley record — recorded as *relayed (secondary)*, **UNVERIFIED** until a primary evidence entry is added | reported contents: 8,484 RGB images, 13 videos, Mumbai + Nashik, potholes / speed breakers / barriers / paved-unpaved; **label format unknown until profiled**; not hosted on Kaggle (you upload it as a private Dataset) |
| **priority (real)** | **RDD2022 India** (`rdd2022`) | real | AI-1 image evaluation (D40 → `roads/pothole`; cracks → `roads` only) | README *CC BY-SA 4.0* vs external *CC BY 4.0* — **unresolved**, treated as the stricter BY-SA | single-country copy: use `default_country='India'`; holdout by index-block groups (a heuristic) |
| secondary (real) | **RDD2020 India** (`rdd2020`) | real | same, earlier release | *CC BY-NC 3.0* reported by a secondary source — **unverified**, NonCommercial | separate card/mapping/ids from RDD2022; never share licence assumptions |
| secondary (real) | **BharatPotHole** (`bharatpothole`; iWatchRoad, Kaggle `surbhisaswatimohanty/bharatpothole`) | real | AI-1 image evaluation, dashcam frames | README (fetched, primary) states **no dataset licence**; the repo *code* licence (CC BY-NC-SA 4.0) is **not** assumed to cover the data | **publishable evaluation disabled** until the dataset's own licence is verified; likely positive-only; frames from videos ⇒ whole-video holdouts |
| **primary (synthetic)** | **BMC Mumbai** (`bmc_mumbai`; Kaggle competition `mumbai-nagar-seva-bmc-civic-complaint-resolution-2018-2024`) | **third-party SYNTHETIC** | large-scale Mumbai/BMC-*structured* synthetic civic data: pipeline/stress testing, taxonomy coverage, routing/triage pipeline tests, analytics demos, leakage testing | competition rules **not read** | **not real, not official BMC data, never real-world validation** (see below); test target withheld; exact generation method/host wording still to be recorded from the primary pages |
| future | **IIIT-H IDD** (`idd`) | real | none in V1 | unverified (variants differ) | documented only; `prepare idd` is refused |
| (optional) | NYC 311, Chicago 311 | real | non-Indian structured sources kept for plumbing/duplicate-pair work | unverified | see below |

**Correction recorded on 2026-10-01:** the Kaggle competition information (relayed by the repository owner; this tooling could not fetch Kaggle, so the card tags it *secondary*, not primary) states that the BMC dataset is **synthetically generated**, not a collection of actual BMC complaint records. The card is therefore `kind: synthetic_third_party`, `origin_status: SYNTHETIC_PER_COMPETITION`; its records carry provenance kind `synthetic_third_party`, which (a) can never satisfy a `real_holdout`/hybrid check, (b) is never mixed with this project's own synthetic data (`synthetic`) in one report, and (c) is evaluated on the `synthetic` track (pipeline tests) or `descriptive` track (taxonomy coverage), with banner "THIRD-PARTY SYNTHETIC DATA … not real-world accuracy". Its description column cannot be confirmed as citizen-written, so `--confirm-citizen-text` is refused. The column-role policy below is unchanged on purpose, so it stays safe on any future real municipal data.

### BMC Mumbai (synthetic): leakage design (the part that matters)

Category, department and severity are **potential targets, not automatic input features**. Mechanisms (all tested in `tests/test_ds_bmc.py`):

1. **Column roles with phases.** Every column is assigned a role (by alias, or explicitly by `--role-map` read from the data dictionary): `identifier`/`at_submission` < `post_triage` < `post_resolution`, plus `sensitive_attribute` (complainant profile) and `pii_never_read`. Ambiguous alias matches **fail loudly** (use `--role-map`); columns no role claims are **unclassified and default-denied for every task**.
2. **Default-deny task allowlists** (`mappings/bmc_mumbai_columns.v1.json`). Each task lists its inputs, targets and forbidden roles; `TaskPolicy.validate` rejects any policy where an input is also a target, is forbidden, is later than the task's `max_phase`, or is sensitive/PII, and where an evaluation/descriptive task takes post-resolution inputs. `TaskPolicy.view` / `.read` are the only sanctioned access paths and raise `LeakageError` otherwise; all BMC evaluation functions use them.
3. **Never stored/read:** PII (names, contacts, contractors/officers) and complainant-profile columns are never read or stored; `resolution_remarks` (post-resolution free text) is never stored; citizen-satisfaction columns are not stored (task `not_pursued`, out of V1 scope). The free-text `description` is stored **only** with `--confirm-citizen-text` after you inspect it, and the intake task then audits label echo.
4. **`CaseRecord.department` is left empty.** Filling it from our taxonomy would make "category → department" a circular routing target. The source's department is kept only as `source_agency`.
5. **Leakage audits** run at prepare time and via `cli leakage-audit`: target determinism (a target ≥ 99% determined by its allowed inputs ⇒ the evaluation is *blocked* as vacuous — the invented fixture's severity/department trip this on purpose), split straddle / spatiotemporal twins, text-echo rate, censoring (unresolved complaints are right-censored, never silently dropped), and `views_clean`.
6. **Claims.** The data is synthetic: `claims_for` never allows a real-world claim for it, and a real-origin-unverified source (should one ever be added) is blocked the same way. BMC pipeline tasks run on the `synthetic` track, taxonomy coverage on `descriptive`; neither mixes with real or project-synthetic rows.

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

**Still not available anywhere here:** real Hindi/Marathi/Hinglish citizen narratives (BMC is synthetic; this project's Hindi/Marathi/Hinglish text is synthetic too), real before/after resolution evidence (AI-4 tested with scripted fixtures only; a *synthetic* before/after set is not generated yet — listed as a GAP in the task matrix), severity ground truth.

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

## Kaggle workflow (datasets stay in `/kaggle/input`; nothing is downloaded locally)

Notebook: [`ai/training/notebooks/05_kaggle_real_data_profile_evaluate.ipynb`](../../notebooks/05_kaggle_real_data_profile_evaluate.ipynb) — a thin wrapper over `kaggle_run.py` (`python -m ai.training.src.data_sources.kaggle_run --help`). CPU only, Internet Off is fine, no GPU, **no model/provider call by default**.

```
BMC synthetic civic ──▶ profile → column roles → mapping → leakage audit → synthetic-track evaluation
Mumbai/Nashik       ──▶ profile-images → format/class names → group-safe holdout → annotation+duplicate audits → real_holdout readiness
RDD2022 India       ──▶ (same; VOC is the documented format, confirmed by the profile)
RDD2020 India       ──▶ (same, optional)
BharatPotHole       ──▶ profile → licence gate → (format/class names/group rule from you) → readiness; publishing disabled while licence unknown
```

* **Dataset by dataset.** Attach any subset; each runs independently and returns `OK`, `PARTIAL`, `NOT_ATTACHED` (with the exact name hints, what *is* attached, how to attach, expected layout), `NEEDS_CONFIG` (a role/format/class-names/group rule/data file you must state — never guessed), `NEEDS_TERMS` (you have not accepted terms), `BLOCKED` or `FAILED` (unexpected error, reported verbatim, other datasets continue).
* **Read in place.** `kaggle_inputs.py` finds mounts under `/kaggle/input/<slug>`, `/kaggle/input/datasets/<owner>/<slug>` and `/kaggle/input/competitions/<slug>` by name **and** structure, never modifies them, and never copies them. Outputs go to `/kaggle/working/civic_real/<dataset>/` (outside the repo; the output guard still applies). Only reports/manifests are bundled; `records.jsonl` and images are excluded by construction.
* **Image audits** (`image_audit.py`, aggregates only): formats by magic bytes vs extension, dimensions, missing/unreadable files, class distribution (raw and mapped), unannotated images vs images with no boxes, box-size distribution, group (video/sequence/block) sizes, **exact duplicates (sha1)** and **near duplicates (64-bit difference hash, needs Pillow, capped & stated)** — including how many duplicate pairs/clusters span groups or the train/holdout split. Any cross-split duplicate **blocks** the `real_holdout` readiness.
* **Holdouts.** RDD uses seeded hashing of index-block groups; other image datasets only get a holdout when you give an explicit group rule (`dir`/`regex`/`block`); without one the run still profiles/prepares but builds **no** split and says so.
* **`real_holdout` readiness** is a verdict, not a result: `can_run_real_holdout` (annotated holdout exists, no straddling groups, no cross-split duplicates) vs `publishable_evaluation_enabled` (also needs a verified licence, ≥ 200 annotated holdout images, and negatives for precision). Today the second is always false.
* **Provider evaluation** (`RUN_PROVIDER_EVAL`) is opt-in and only attempted when readiness allows; a missing provider is a skipped stage, never a failure.

| dataset | attach in Kaggle | expected under `/kaggle/input/` |
|---|---|---|
| `bmc_mumbai` | Add Input → Competition data (accept the rules first) | `competitions/mumbai-nagar-seva-bmc-civic-complaint-resolution-2018-2024/` containing one `*train*.csv` (+ data dictionary; the test CSV's target is withheld and unused) |
| `mumbai_nashik_road_surface` | upload the Mendeley files as a **private** Kaggle Dataset (keep attribution/licence text), then Add Input | `<your-dataset>/…` (name containing `nashik`/`mumbai`/`roadsurface`/`tj2m7zz4rg`, or pass `PATHS`) with images (+ annotations/folders/videos) |
| `rdd2022` | private/trusted Kaggle Dataset of the **India** subset | `<name containing rdd2022>/…/India/train/{images,annotations/xmls}` (or the mount *is* the India folder) |
| `rdd2020` | Kaggle Dataset of the RDD2020 **India** subset | `<name containing rdd2020>/…/India/train/{images,annotations/xmls}` |
| `bharatpothole` | Add Input → Datasets → `surbhisaswatimohanty/bharatpothole` | `bharatpothole/…` frames + annotations (format *not assumed*: profile first; YOLO needs the dataset's class-names file) |

Copies of RDD/Mumbai-Nashik uploaded by third parties have **their own provenance**: record who published the copy before trusting it, and re-check the licence at the primary record.

## Not verified / blocked in the authoring environment
* Official pages for NYC 311, Chicago 311 and figshare were **unreachable** (egress proxy). Their licence/column/format details above come from web-search summaries or are expectations, tagged as such in the cards.
* No real data was downloaded or used; all adapter/evaluation tests run on invented format fixtures.
* Mapping tables are hypotheses until validated with `profile` on the real files. BMC column names, class names for BharatPotHole / Mumbai-Nashik, and the BMC category list (user-reported) are **expectations**, not read from the files.
* Kaggle, Mendeley, figshare and IIIT-H were unreachable; BharatPotHole's repository README (GitHub) was the only primary source fetched for the Indian datasets. The BMC *synthetic* statement and the Mumbai/Nashik *CC BY 4.0* licence are owner-relayed (secondary) until quoted from the primary pages.
