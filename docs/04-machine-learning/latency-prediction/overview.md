---
Status: Implemented
Owner: Platform
Last updated: 2026-08-10
---

# Latency prediction

## Intent

Predict workload **`latency_ms`** (point estimate) for SLO-aware cost estimation when measured latency is unavailable. Percentile heads (p95/p99) remain a follow-on once online latency histograms exist.

## Implemented now

1. **Target / label:** `latency_ms` from `Cloud_Dataset.csv` (same temporal train/test split as cost).
2. **Model class:** `RandomForestRegressor` (shared hyperparams with cost RF). Features **exclude** `latency_ms` and `latency_throughput_ratio` (no label leakage).
3. **Evaluation:** `artifacts/model_trainer/latency_metrics.json` (MAE/RMSE/R² train+test+gaps+OOB). Logged to MLflow as `latency_*` metrics. **Not** used by cost packaging gates.
4. **CAS:** Optional adjunct blobs on the same package version — `latency_model.pkl`, `latency_feature_columns.json`, `latency_metrics.json`. Cost `digest_ring` still seals only the four core cost blobs.
5. **Serving:**
   - `POST /api/predict/latency` → `predicted_latency_ms`
   - `POST /api/predict` may omit `latency_ms`; server fills from the latency model (`latency_ms_source=model`)
   - `/ops/model-card` and `/health` expose latency offline metrics + load flag
   - Prometheus: `latency_model_loaded`, `latency_predict_requests_total`

## Caveats

- Synthetic ~1k-row dataset → optimistic holdout scores; treat as plumbing, not FinOps truth.
- Point estimate only (not calibrated p95). Next: quantile regression or conformal intervals when real telemetry arrives.
