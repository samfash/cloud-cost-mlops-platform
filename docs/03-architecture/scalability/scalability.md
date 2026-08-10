---
Status: Partial
Owner: Platform
Last updated: 2026-08-10
---

# Scalability

## Current posture

- Gunicorn `1` worker / `8` threads (coherent in-process Prometheus + predict cache)
- Sync **batch** endpoint for up to 500 instances per call
- Compose `cpus` / `mem_limit`
- Optional canary/shadow does not require extra replicas

## Limits

- Workers > 1 needs multiprocess metrics + shared cache
- CAS on local volume — not shared object storage
- No HPA / k8s yet

> Next (needs you): k6 soak; Redis cache; K8s Deployment + HPA — see `docs/USER_ACTIONS.md`.
