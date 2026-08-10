---
Status: Implemented
Owner: Platform
Last updated: 2026-08-10
---

# Logging

## Contract

Both services emit **one JSON object per line** to **stdout** (container-friendly).

Common fields:

| Field | Meaning |
|-------|---------|
| `ts` | UTC ISO timestamp |
| `level` | INFO/ERROR/... |
| `logger` | Logger name |
| `message` | Human message |
| `request_id` | Correlation id |
| `path` / `method` / `status` | HTTP access fields |
| `latency_ms` | Request duration |
| `service` | `cloud-cost-api` or `model-lab-api` |

## Configuration

| Env | Default | Effect |
|-----|---------|--------|
| `LOG_LEVEL` | `INFO` | Root log level |
| `LOG_TO_FILE` | `0` | When `1`, also write under `./logs/*.log` |

## Notes

- File-only logging (and the nested `logs/<name>.log/` directory bug) has been removed.
- Prefer scraping container stdout via Docker/K8s log drivers; do not rely on in-container files in production.
