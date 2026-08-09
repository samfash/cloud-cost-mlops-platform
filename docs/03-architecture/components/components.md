---
Status: Implemented
Owner: Platform
Last updated: 2026-08-09
---

# Components

## cloud-cost

| Component | Responsibility |
|-----------|----------------|
| `data_validation` | Schema/status checks on CSV |
| `data_transformation` | Encoders, feature eng, train/test split |
| `model_trainer` | Fit RandomForest from `params.yaml` |
| `model_evaluation` | Holdout MAE/MSE/RMSE/R² |
| `model_packager` | CAS publish + gates |
| `PredictionPipeline` | Load HEAD bundle, predict |
| `dependency_tracker` | Git-blob digests / skip |

## model_lab

| Component | Responsibility |
|-----------|----------------|
| `selector` / REXX | Borda & Copeland election |
| `cli` | Build submission offline |
| Flask `app` | `/api/select` |
