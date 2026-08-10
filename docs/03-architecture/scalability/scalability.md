---
Status: Partial
Owner: Platform
Last updated: 2026-08-10
---

# Scalability

## Current posture

Single Compose stack with Gunicorn (`1` worker / `8` threads on inference for coherent in-process Prometheus metrics; `max-requests` recycling). RF inference is CPU-bound and cheap per row for this feature width. Compose applies `cpus` / `mem_limit` to bound noisy neighbors.

## Limits

- No horizontal pod autoscaling / multi-replica shared metrics yet
- CAS on local volume — not shared object storage
- Training inside image build couples build time to data size
- Optional in-process rate limit is per-replica (not a distributed gateway)

> **GAP:** No load test results or HPA configs. Next: k6 script against `/api/predict`; define RPS budget; move metrics to a sidecar or Prometheus multiprocess mode before scaling workers > 1.
