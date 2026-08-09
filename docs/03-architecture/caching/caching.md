---
Status: Partial
Owner: Platform
Last updated: 2026-08-09
---

# Caching

## Implemented

- Pipeline stage skip via content digests (compute cache)
- Docker image layers
- Compose volume reuse for artifacts

## Not implemented

- HTTP response cache for predictions
- Feature/result Redis cache
- CDN

> **GAP:** No prediction cache layer. Next: measure p95 latency; only add cache if idempotent GETs are introduced (today predict is POST).
