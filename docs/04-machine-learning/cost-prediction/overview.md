---
Status: Implemented
Owner: Platform
Last updated: 2026-08-10
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
| oob_score | true |

## Split & leakage controls

- Default `SPLIT_MODE=temporal` (time-ordered 80/20)
- Excludes `cost`, `price_per_hour`, `cost_to_price_ratio`
- Feature `target` = operational scale intent (not the label)

## Offline metrics (representative temporal holdout)

| Metric | Typical value |
|--------|----------------|
| MAE | ≈ 0.00126 |
| RMSE | ≈ 0.00206 |
| R² | ≈ 0.9987 |
| gap_R2 (train−test) | ≈ 0.0009 |
| Dummy-mean MAE lift | ≈ 0.05 |

Packaging / CI floors: `r2_floor=0.90`, `mae_ceiling=0.05`.

> **Caveat:** ~1000-row synthetic dataset — optimistic vs real cloud bills.

## Serving

`PredictionPipeline` loads sealed CAS HEAD (optional probe for canary/shadow).  
Flask: `/api/predict`, `/api/predict/batch`, `/ops/model-card`.
