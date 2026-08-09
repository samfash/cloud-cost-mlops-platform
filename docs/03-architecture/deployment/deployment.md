---
Status: Partial
Owner: Platform
Last updated: 2026-08-09
---

# Deployment view

## Implemented

- Single-host Docker Compose
- Image build trains/packages during `docker build`
- Named volume `model-artifacts` for CAS persistence
- Healthcheck on `:8080/health`

## Not implemented

- Kubernetes / Helm
- Multi-region active-active
- Managed secrets store
- Blue/green or canary at ingress

> **GAP:** No K8s manifests or IaC (Terraform). Next: sketch Deployment+Service YAML reading CAS from PVC.
