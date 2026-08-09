---
Status: Partial
Owner: Platform
Last updated: 2026-08-09
---

# Deployment

## Implemented

```bash
docker compose up --build -d
docker compose --profile train run --rm train
docker compose --profile test run --rm test
```

- Image: `cloud-cost-api:latest`
- Volume: `model-artifacts` → `/app/cloud-cost/artifacts`

## Gap

> **GAP:** No cloud deploy runbook (ECS/EKS/Cloud Run). Next: pick one target and write a 1-page deploy checklist.
