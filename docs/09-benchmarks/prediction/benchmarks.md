---
Status: Partial
Owner: Platform
Last updated: 2026-08-09
---

# Prediction benchmarks

## Implemented snapshot

| Metric | Value | Dataset |
|--------|-------|---------|
| MAE | ~0.00116 | holdout synthetic |
| RMSE | ~0.00182 | holdout synthetic |
| R² | ~0.999 | holdout synthetic |

## Methodology notes

- Single train/test split from transformation stage
- Not nested CV; not temporal backtest

> **GAP:** No public leaderboard, no baseline linear model comparison checked into `09-benchmarks`. Next: add Ridge/Dummy baselines table.
