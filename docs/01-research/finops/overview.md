---
Status: Partial
Owner: Platform
Last updated: 2026-08-09
---

# FinOps research notes

## Principles we already support

1. **Traceability:** CAS digests and RELEASES ledger
2. **Change control:** promotion gates (R² / MAE / schema)
3. **Operational efficiency:** dependency skip digests

## Principles not yet supported

- Real CUR / export ingestion
- Allocation tags and shared-cost splitting
- Budget alerts and anomaly detection on live spend

> **GAP:** Synthetic CSV only — not linked to billing accounts. Next actions: define a `BillingEvent` schema; spike AWS CUR → Parquet loader offline.
