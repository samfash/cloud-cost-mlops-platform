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
- Leakage exclusions (`cost`, `price_per_hour`, `cost_to_price_ratio`)
- Temporal holdout by default (`SPLIT_MODE=temporal`)
- Predict-time feature range monitor → logs + Prometheus (`feature_out_of_band_*`)
- Offline PSI helper for batch jobs (`population_stability_index`)

## Missing

- Great Expectations / Deequ suites
- Online residual monitoring vs realized invoices
- PII classification (synthetic today)

> Remaining: wire OOB rate into on-call (Alertmanager) and add label-feedback DQ.
