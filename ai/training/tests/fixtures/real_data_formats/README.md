# Format fixtures — NOT REAL DATA

These files contain **invented rows** (IDs start with `FMT-`) that only mimic the *shape* (column names, date formats,
value styles) the real-data adapters expect. They exist so the adapters and evaluation harness can be unit-tested
without downloading or committing any real public dataset. Column names are an UNVERIFIED expectation of the real
files; confirm them with `python -m ai.training.src.data_sources.cli profile ...` on the real download.

Never treat these rows as evidence about NYC, Chicago or RDD2022.

`bmc_mumbai_format_sample.csv` (120 invented rows, ids `FMT-B*`) mimics the *kind* of columns the BMC Kaggle file is reported to have. It deliberately contains
**leakage traps** so the guards can be tested: `severity` and `department` are deterministic functions of the category; `resolution_remarks` echoes the category; every 5th
`complaint_description` echoes its label; ~30% of complaints are unresolved (right-censored); `complainant_*` (sensitive) and `*_name` (PII) columns exist; one column
(`UNCLASSIFIED_SENTINEL_COL`) is claimed by no role and must never appear in any output. It says nothing about the real file.
