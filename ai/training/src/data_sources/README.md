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

## Datasets investigated (details in `cards/*.json`)

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
| `adapters/` | `nyc311`, `chicago311` (tabular), `rdd2022` (PASCAL VOC → image references + boxes), `synthetic` (wrap generator rows). Address columns are never read |
| `download/` | `socrata.py` (bounded, paged, auditable `RETRIEVAL.json`, no token written), `figshare.py` (list/licence/size-guarded download with md5) — external dirs only |
| `profile.py` | pre-flight: columns, value space, free-text candidates, date/coordinate coverage, draft mapping coverage |
| `splits.py` | time / group (country, district) / spatial-cell holdouts so near-identical rows cannot straddle train and test |
| `pairs.py` | real duplicate pairs from agency parent links + sampled unlinked negatives |
| `hybrid.py` | leakage-guarded real+synthetic training-set assembly |
| `paths.py` | **output guard**: only outside the repo or `ai/artifacts/real_data/` (gitignored); everything else is refused |
| `cli.py` | `cards`, `card`, `download`, `figshare-*`, `profile`, `prepare`, `pairs` |

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

## Not verified / blocked in the authoring environment
* Official pages for NYC 311, Chicago 311 and figshare were **unreachable** (egress proxy). Their licence/column/format details above come from web-search summaries or are expectations, tagged as such in the cards.
* No real data was downloaded or used; all adapter/evaluation tests run on invented format fixtures.
* Mapping tables are hypotheses until validated with `profile` on the real files.
