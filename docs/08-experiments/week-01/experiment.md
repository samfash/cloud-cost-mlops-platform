---
Status: Implemented
Owner: Platform
Last updated: 2026-08-09
---

# Week 01 — Baseline pipeline & dataset

## Hypothesis

A RandomForest on engineered VM features can fit synthetic cloud cost with high holdout R².

## Work

- Wired validation → transform → train → evaluate
- Locked params (`n_estimators=300`, `max_depth=20`, …)
- Established `Cloud_Dataset.csv` as fixture

## Result

Holdout R² ≈ 0.999, MAE ≈ 0.00116 — flagged as synthetic optimism.
