---
Status: Partial
Owner: Platform
Last updated: 2026-08-10
---

# Observability

## Implemented now

| Signal | Where |
|--------|--------|
| Structured JSON logs to stdout | `cloud-cost` + `model_lab` |
| `X-Request-Id` propagation | Both APIs (request + response header) |
| Prometheus `/metrics` | `:8080/metrics`, `:8081/metrics` |
| Readiness probes | `:8080/ready`, `:8081/ready` |
| Checked-in alert rules | `deploy/prometheus/alerts.yml` |
| Optional Prometheus + Grafana | `docker compose --profile obs up` |
| Starter Grafana dashboard | `deploy/grafana/dashboards/cloud-cost-overview.json` |

### Key metrics (inference)

- `http_requests_total{service,method,endpoint,status}`
- `predict_requests_total{service,outcome}`
- `predict_latency_seconds{service}`
- `predict_errors_total{service,error_class}`
- `model_loaded{service}`

### Key metrics (model lab)

- `model_lab_http_requests_total`
- `model_lab_select_requests_total{outcome}`

### Local obs stack

```bash
docker compose --profile obs up -d
# Prometheus http://localhost:9090
# Grafana    http://localhost:3000  (anonymous Viewer enabled)
```

## Still open (GAP)

> **GAP:** Distributed tracing (OpenTelemetry), SLO burn-rate recording rules, and log aggregation (Loki/ELK) are not deployed yet.
>
> Next actions:
> 1. Add OTel middleware on `/api/predict`
> 2. Add recording rules for error-budget burn
> 3. Ship Loki (or equivalent) beside the Compose `obs` profile
