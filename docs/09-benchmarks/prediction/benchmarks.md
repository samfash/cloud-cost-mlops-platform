---
Status: Partial
Owner: Platform
Last updated: 2026-08-10
---

# Prediction benchmarks

## Implemented

- Holdout metrics in `artifacts/model_evaluation/metrics.json` (MAE/RMSE/R²)
- Train/test gap + DummyRegressor mean baseline lift
- CI gate vs packaging floors
- Temporal split default (more honest than random on timed rows)

## Interpretation

Precision/recall **do not apply** (regression). Prefer MAE/RMSE/R² and gap_R2.

> Still open: public leaderboard, real-invoice provider accuracy study, Ridge baseline table checked into docs.
