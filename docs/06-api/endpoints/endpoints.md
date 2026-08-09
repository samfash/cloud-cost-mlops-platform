---
Status: Implemented
Owner: Platform
Last updated: 2026-08-09
---

# Endpoints

## Cloud-cost `:8080`

| Method | Path | Body | Response |
|--------|------|------|----------|
| GET | `/` | — | HTML form |
| GET | `/health` | — | JSON model/bundle status |
| POST | `/predict` | form-encoded | HTML results |
| POST | `/api/predict` | JSON features | `prediction`, `status` |

## Model lab `:8081`

| Method | Path | Body | Response |
|--------|------|------|----------|
| GET | `/health` | — | `status`, `service` |
| POST | `/api/select` | optional paths JSON | `chosen` trial |

See [openapi/openapi.yaml](openapi/openapi.yaml).
