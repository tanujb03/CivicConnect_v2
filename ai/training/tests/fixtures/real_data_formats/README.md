# Format fixtures — NOT REAL DATA

These files contain **invented rows** (IDs start with `FMT-`) that only mimic the *shape* (column names, date formats,
value styles) the real-data adapters expect. They exist so the adapters and evaluation harness can be unit-tested
without downloading or committing any real public dataset. Column names are an UNVERIFIED expectation of the real
files; confirm them with `python -m ai.training.src.data_sources.cli profile ...` on the real download.

Never treat these rows as evidence about NYC, Chicago or RDD2022.
