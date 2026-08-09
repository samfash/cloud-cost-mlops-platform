---
Status: Gap
Owner: Platform
Last updated: 2026-08-09
---

# Scalability

## Current posture

Single Compose stack, one API process model (Gunicorn in container as packaged). RF inference is CPU-bound and cheap per row for this feature width.

## Limits

- No horizontal pod autoscaling
- CAS on local volume — not shared object storage
- Training inside image build couples build time to data size

> **GAP:** No load test results or HPA configs. Next: k6 script against `/api/predict`; define RPS budget.
