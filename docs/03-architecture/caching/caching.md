---
Status: Partial
Owner: Platform
Last updated: 2026-08-10
---

# Caching

## Implemented

- Pipeline stage skip via content digests (compute cache)
- Docker image layers
- Compose volume reuse for artifacts
- **In-process prediction cache** for identical POST payloads (`cloud-cost/src/predict_cache.py`)
  - Keyed by SHA-256 of canonical JSON + `model_version`
  - LRU + TTL (defaults: 1024 entries, 300s)
  - Toggle: `PREDICT_CACHE_ENABLED` / `PREDICT_CACHE_SIZE` / `PREDICT_CACHE_TTL_SECONDS`
  - Metrics: `predict_cache_hits_total`, `predict_cache_misses_total`, `predict_cache_entries`
  - Response field: `cache_hit` on `/api/predict` (additive)

## Not implemented

- Shared Redis / Memcached across replicas
- CDN for static UI assets
- HTTP cache semantics for POST (intentionally avoided)

> Remaining: multi-replica shared cache when workers/replicas > 1.
