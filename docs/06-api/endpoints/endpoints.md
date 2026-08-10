---
Status: Implemented
Owner: Platform
Last updated: 2026-08-10
---

# Endpoints

## Cloud-cost `:8080`

| Method | Path | Body | Response |
|--------|------|------|----------|
| GET | `/` | — | Non-technical HTML overview |
| GET | `/estimate` | — | Corporate estimate wizard |
| GET | `/health` | — | JSON model/bundle status (liveness-oriented, always 200 if process up) |
| GET | `/ready` | — | `200` when model loaded; `503` otherwise (orchestration probe) |
| GET | `/metrics` | — | Prometheus text exposition |
| POST | `/predict` | form-encoded | HTML results |
| POST | `/api/predict` | JSON features | `prediction`, `status`, plus additive `model_version`, `variant`, `request_id`, `latency_ms`, `cache_hit` |
| POST | `/api/predict/batch` | `{"instances":[...]}` | per-row predictions (≤500) |
| GET | `/ops/model-card` | — | Offline metrics + online serving posture |

Notes:

- Invalid JSON / missing fields → **400** `{"error": "..."}`
- Model unavailable → **503** `{"error": "..."}`
- All responses include `X-Request-Id` (echo or generated)
- Optional `API_KEY`; Compose defaults `RATE_LIMIT_PER_MINUTE=600` (set `0` to disable) → **401** / **429**
- Probes + `/` + `/estimate` stay open when `API_KEY` is set
- Identical payloads may return `cache_hit: true` from the in-process prediction cache

## Model lab `:8081`

| Method | Path | Body | Response |
|--------|------|------|----------|
| GET | `/health` | — | `status`, `service`, `ready` |
| GET | `/ready` | — | election assets present |
| GET | `/metrics` | — | Prometheus text |
| POST | `/api/select` | optional paths JSON | `chosen` trial + `request_id` |

See [openapi/openapi.yaml](openapi/openapi.yaml).

## Still open (GAP)

> **GAP:** No webhooks or generated SDKs yet. Multi-tenant AuthZ remains open (optional shared `API_KEY` is the current control).
