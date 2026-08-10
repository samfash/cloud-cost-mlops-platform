---
Status: Partial
Owner: Platform
Last updated: 2026-08-10
---

# Monitoring

## Implemented

- Prometheus scrape + alert rule load: `deploy/prometheus/`
- Compose profile `obs` runs Prometheus + Grafana against both APIs
- Starter dashboard: `deploy/grafana/dashboards/cloud-cost-overview.json`
- Readiness endpoints for orchestration probes

### Suggested red/yellow signals

| Signal | Healthy | Investigate |
|--------|---------|-------------|
| `model_loaded` | 1 | 0 → inference unavailable |
| `predict_requests_total{outcome="error"}` rate | ~0 | rising errors |
| `predict_latency_seconds` p95 | < 100ms (local RF) | regression / resource pressure |
| `/ready` | 200 | 503 |

## Still open (GAP)

> **GAP:** No formal SLO burn-rate recording rules or long-term metric retention volume.
>
> Next actions: define availability SLO (≥99.9% ready) and latency SLO (p95 < 250ms); add a persistent Prometheus volume.
