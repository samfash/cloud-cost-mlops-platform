---
Status: Partial
Owner: Platform
Last updated: 2026-08-10
---

# Deployment

## Implemented

- Multi-service **Docker Compose**: `api` (Gunicorn), `model-lab` (Gunicorn), optional `prometheus` + `grafana` (`--profile obs`)
- Image builds train + package the model, seeds `/opt/seed` for empty volumes
- Entrypoint seeds CAS artifacts, fixes volume ownership, drops to `appuser` (uid 10001)
- Process manager: **tini** + Gunicorn (`timeout`, `max-requests`, access/error logs to stdout)
- Health: Compose/Docker probes hit **`/ready`** (not a lying `/health` when model is missing)
- Resource limits via Compose `cpus` / `mem_limit` (+ Swarm `deploy.resources`)
- Optional `API_KEY` and `RATE_LIMIT_PER_MINUTE` env vars (off by default)

## Run

```bash
docker compose up --build -d
docker compose --profile obs up -d          # + Prometheus :9090 + Grafana :3000
docker compose --profile train run --rm train
docker compose --profile test run --rm test
```

## Still open (GAP)

> **GAP:** No Kubernetes manifests, HPA, or ingress TLS yet.
>
> Next actions:
> 1. Add `deploy/k8s/` Deployment + Service + PVC for CAS store
> 2. Ingress with TLS
> 3. Horizontal Pod Autoscaler on CPU + p95 predict latency
