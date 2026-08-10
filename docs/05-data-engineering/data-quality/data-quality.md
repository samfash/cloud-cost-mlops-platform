---
Status: Partial
Owner: Platform
Last updated: 2026-08-10
---

# Data quality

## Implemented

- Validation stage writes status
- Output validators (CSV has `cost`, pickle loadable, metrics keys present)
- Packaging refuses missing metric keys / floor-ceiling breaches
- **Predict-time feature range monitor** (`cloud-cost/src/feature_monitor.py`)
  - Compares numeric inputs to training CSV p01–p99 bands (fallback defaults)
  - Log-only warnings (`feature_out_of_band`); does not reject traffic

## Missing

- Great Expectations / Deequ suites
- Full PSI dashboards / alerting on drift volume
- PII classification (synthetic today)

> Remaining: promote out-of-band rate into a Prometheus gauge and ticket alert.
