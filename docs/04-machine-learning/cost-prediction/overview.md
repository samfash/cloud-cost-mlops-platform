---
Status: Implemented
Owner: Platform
Last updated: 2026-08-09
---

# Cost prediction (IMPLEMENTED)

## Objective

Regress continuous VM **`cost`** from utilization, sizing, and categorical cloud features.

## Algorithm

`sklearn.ensemble.RandomForestRegressor` with params from `cloud-cost/params.yaml`:

| Param | Value |
|-------|-------|
| n_estimators | 300 |
| max_depth | 20 |
| min_samples_split | 5 |
| min_samples_leaf | 2 |
| max_features | sqrt |
| random_state | 42 |

## Observed holdout metrics

From `artifacts/model_evaluation/metrics.json` (representative run):

| Metric | Value |
|--------|-------|
| MAE | ≈ 0.00115786 |
| MSE | ≈ 3.31e-6 |
| RMSE | ≈ 0.00181872 |
| R² | ≈ 0.998964 |

> **Caveat:** ~1000-row synthetic dataset — metrics are optimistic and not proof of production accuracy.

## Serving

`PredictionPipeline` loads sealed bundle from CAS HEAD; Flask exposes `/api/predict`.
