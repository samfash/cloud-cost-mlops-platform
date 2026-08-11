---
Status: Partial
Owner: Platform
Last updated: 2026-08-10
---

# 07 — Infrastructure

Compose + Gunicorn + GitHub Actions are production-leaning. Structured logs, `/ready`, `/metrics`, CAS backup/restore (CI drill), Prometheus alert rules, and an optional Prometheus + Grafana profile are in place. Alertmanager paging, CD, and Kubernetes remain open.

## Contents

- [Render deploy v1](render/deploy-v1.md) — **operator checklist** (secrets, plan, verification)
- [Deployment](deployment/deployment.md) — Compose, Gunicorn, non-root drop, resource limits
- [CI/CD](ci-cd/ci-cd.md) — GHA unit/integration/docker compose + obs smoke + Trivy
- [Observability](observability/observability.md) — metrics, request ids, Grafana dashboard
- [Logging](logging/logging.md) — JSON stdout contract
- [Monitoring](monitoring/monitoring.md) — Prometheus + Grafana profile
- [Alerts](alerts/alerts.md) — checked-in Prometheus rules
- [Disaster recovery](disaster-recovery/disaster-recovery.md) — CAS backup/restore + CI drill
