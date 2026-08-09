---
Status: Partial
Owner: Platform
Last updated: 2026-08-09
---

# ETL

## Implemented

In-process Python transforms (pandas) from local CSV — not a distributed ETL grid.

## Planned

Billing export ETL (CUR → Parquet → feature tables).

> **GAP:** No Airflow/Dagster/Spark jobs. Next: keep CSV path; add optional Parquet reader interface.
