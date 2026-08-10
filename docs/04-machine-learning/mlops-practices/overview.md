---
Status: Implemented
Owner: Platform
Last updated: 2026-08-10
---

# MLOps practices (cloud-cost)

How this repo treats the classic MLOps concerns for **VM cost regression**.

## Training vs inference

| Concern | Approach |
|---------|----------|
| Shared transforms | `src/utils/feature_engineering.py` used by training + `CustomData` |
| Encoders | Fit only in `data_transformation`; serve reuses `label_encoders.pkl` |
| Column order | Packaged `feature_columns.json` + reindex at predict |
| Parity test | `tests/unit/test_train_serve_parity.py` |
| Schema contract | Local feature-store snapshot under `artifacts/data_transformation/feature_store/` |

## Batch vs real-time

| Mode | Entry |
|------|-------|
| Real-time | `POST /api/predict` |
| Sync batch | `POST /api/predict/batch` (`instances` ≤ 500) |
| Offline CLI | `scripts/batch_infer.py` (local CAS or HTTP) |

Async job queues / Spark scoring are **not** in scope.

## Model drift & monitoring

- Predict-time **range OOB** checks → logs + `feature_out_of_band_*` Prometheus counters
- Alert rule `CloudCostFeatureDriftOOB`
- Offline helper `population_stability_index()` for batch PSI jobs
- **Not yet:** label drift (needs ground-truth costs online)

## Feature stores

Local **schema snapshot** only (`src/feature_store.py`). Not Feast/Tecton/Vertex.

## CI/CD for ML

1. Unit + train/package (`SPLIT_MODE=temporal`)
2. `scripts/check_metrics_gate.py` vs `r2_floor` / `mae_ceiling`
3. CAS backup drill, API/model-lab tests, Docker compose smoke, Trivy

CD publish/deploy still needs your registry credentials.

## Experiment tracking

MLflow (local `mlruns/`): params + train/test/gap/baseline metrics + model artifact in evaluation stage.

## A/B testing (canary / shadow)

CAS `pins.json` already tracks `anchor` / `probe`. Serving:

| Env | Behavior |
|-----|----------|
| `SERVING_MODE=primary` | HEAD only (default) |
| `SERVING_MODE=shadow` + `CANARY_PERCENT>0` | Score probe, log delta, return primary |
| `SERVING_MODE=canary` + `CANARY_PERCENT` | Route % traffic to probe response |

Requires a distinct probe pin from packaging promotions.

## Data leakage

- Label `cost` (+ near-labels) excluded from features
- Feature named `target` is **scale intent**, not the label
- Default **temporal** holdout (`SPLIT_MODE=temporal`); `random` still available
- Residual: synthetic data + very high R² — validate on real bills before trusting absolute accuracy

## Offline vs online metrics

| Offline | Online |
|---------|--------|
| MAE/RMSE/R², train/test gap, Dummy baseline lift | Latency, errors, cache hits, OOB drift, canary/shadow counters |
| Packaged into CAS + `/ops/model-card` | Prometheus `/metrics` |

Online **accuracy** needs a feedback pipeline of realized costs (user action).

## Precision vs recall

**Not applicable** — task is regression. Gates use MAE/R². Classification P/R would only apply to a separate classifier.

## Bias / variance

Logged `train_*`, `test_*`, `gap_R2`, `gap_MAE`, RF `oob_score`. Small gap on synthetic data; re-check on real distributions.

## Scaling inference

- Gunicorn 1 worker / 8 threads (coherent in-process metrics/cache)
- Predict cache + batch endpoint for fan-in
- Compose CPU/mem limits
- Horizontal scale needs shared cache/metrics story (Redis / multiprocess) — see scalability doc
