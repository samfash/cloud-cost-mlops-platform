---
Status: Gap
Owner: Platform
Last updated: 2026-08-09
---

# Latency prediction

## Intent

Predict service or LLM latency percentiles (p50/p95/p99) for SLO-aware routing.

## Implemented now

`latency_ms` is an **input feature** to the cost model, not a prediction target. No latency model exists.

> **GAP:** Latency-prediction model absent. Next actions:
> 1. Define target (`latency_p95`) and label source
> 2. Choose model class (RF / GBDT / quantile regression)
> 3. Add evaluation suite separate from cost metrics
> 4. Keep CAS packaging contract reusable
