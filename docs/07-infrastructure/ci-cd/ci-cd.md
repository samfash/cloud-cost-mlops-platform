---
Status: Partial
Owner: Platform
Last updated: 2026-08-10
---

# CI/CD

## Implemented (CI)

GitHub Actions (`.github/workflows/ci.yml`):

1. Unit tests (including optional API guards)
2. Train + package smoke
3. CAS backup/restore drill
4. Model-lab CLI submission
5. Integration tests (`/ready`, `/metrics`, `/api/predict`, model-lab select)
6. Docker image build
7. `docker compose` smoke (ready + predict + select)
8. Observability profile smoke (Prometheus alert rules loaded)
9. Trivy image scan (informational; `exit-code: 0`)
10. Ruff lint

## Still open (GAP)

> **GAP:** No CD (image publish to GHCR/ECR), no hard SBOM gate, no staging environment.
>
> Next actions:
> 1. Publish `ghcr.io/<org>/cloud-cost-api` on main
> 2. Fail CI on CRITICAL Trivy findings once baseline is clean
> 3. Deploy-to-staging job after smoke
