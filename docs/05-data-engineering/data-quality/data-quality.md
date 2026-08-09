---
Status: Partial
Owner: Platform
Last updated: 2026-08-09
---

# Data quality

## Implemented

- Validation stage writes status
- Output validators (CSV has `cost`, pickle loadable, metrics keys present)
- Packaging refuses missing metric keys / floor-ceiling breaches

## Missing

- Great Expectations / Deequ suites
- Drift detection vs training distribution
- PII classification (synthetic today)

> **GAP:** No continuous DQ monitors in production. Next: add simple PSI on numeric features at predict time (log-only).
