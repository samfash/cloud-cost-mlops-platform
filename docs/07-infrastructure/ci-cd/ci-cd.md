---
Status: Partial
Owner: Platform
Last updated: 2026-08-10
---

# CI/CD

## Implemented (CI + ML gates)

GitHub Actions (`.github/workflows/ci.yml`):

1. Unit tests (guards, cache, train/serve parity, …)
2. Train + package with `SPLIT_MODE=temporal`
3. **ML metrics gate** (`scripts/check_metrics_gate.py`)
4. CAS backup/restore drill
5. Model-lab CLI submission
6. Integration tests (predict, batch, model-card, select)
7. Docker image build + compose smoke (+ Prometheus rules)
8. Trivy image scan (informational)
9. Ruff lint

## Still open (GAP)

> **GAP:** No CD (GHCR/ECR publish), no staging deploy, Trivy not failing the build yet.
>
> See [USER_ACTIONS.md](../../USER_ACTIONS.md) for registry/secrets steps.
