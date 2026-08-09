---
Status: Gap
Owner: Platform
Last updated: 2026-08-09
---

# Disaster recovery

## Assets to protect

- `artifacts/model_bundle/` (CAS)
- Dataset + params/schema
- Image registry tags

## Current posture

Local/volume backed; recreate via `python main.py` or image rebuild.

> **GAP:** No DR runbook with proven RTO/RPO. Next actions:
> 1. State RTO/RPO targets (e.g. RPO=24h artifacts backup)
> 2. Script CAS tarball backup/restore
> 3. Schedule a restore drill and record results
