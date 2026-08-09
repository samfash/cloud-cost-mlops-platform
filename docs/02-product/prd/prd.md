---
Status: Partial
Owner: Platform
Last updated: 2026-08-09
---

# PRD — Cloud Cost Prediction Platform

## Problem

Teams need a reproducible way to train, seal, and serve VM cost predictions without ad-hoc pickle folders or silent metric regressions.

## Goals (implemented)

1. Train RF regressor on `Cloud_Dataset.csv`
2. Skip unchanged pipeline stages via Git-blob digests
3. Publish only through CAS gates
4. Serve predictions on Flask `:8080`
5. Elect model-lab trials via REXX on `:8081`

## Non-goals

- Dollar-accurate forecasts on production billing (dataset is synthetic)
- Multi-tenant SaaS in v1
- LLM token billing (planned)

## Success metrics

| Metric | Target | Observed |
|--------|--------|----------|
| Holdout R² | ≥ 0.95 (lab) | ~0.999 |
| Holdout MAE | low on scale of `cost` | ~0.00116 |
| CI green | required | unit + train smoke + docker build |
| Stage skip correctness | digests stable | covered by unit/integration tests |

> **Caveat:** Near-perfect metrics reflect a small synthetic dataset; do not claim production accuracy.

## Requirements

### Functional (done)

- Predict `cost` from VM/telemetry features
- Health endpoint exposes bundle version + metrics
- Packaging refuses dual-metric regressions per contract

### Functional (planned)

- AuthN/AuthZ, webhooks, SDKs, LLM cost modules

> **GAP:** No signed-off PRD with stakeholders. Next: ratify goals/non-goals with course/advisor or product owner.
