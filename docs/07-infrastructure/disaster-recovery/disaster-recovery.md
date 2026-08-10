---
Status: Partial
Owner: Platform
Last updated: 2026-08-10
---

# Disaster recovery

## Implemented

CAS backup/restore scripts for the immutable model store:

```bash
./scripts/backup_cas.sh
# -> backups/model_bundle_<timestamp>.tar.gz (+ .sha256)

./scripts/restore_cas.sh backups/model_bundle_<timestamp>.tar.gz
# restart API afterward so HEAD is reloaded
docker compose restart api
```

CI runs a **backup → wipe → restore** drill after the train smoke step and asserts `HEAD` is restored.

| Item | Target (design) | Proven? |
|------|-----------------|---------|
| RPO (model store) | Last successful backup | Partial — scripts + CI drill |
| RTO (restore + restart) | < 15 minutes local/Compose | Partial — restore path exercised in CI; full restart RTO not timed in CI |

## Recovery steps (Compose)

1. Stop API: `docker compose stop api`
2. Restore archive into `cloud-cost/artifacts/model_bundle`
3. Start API: `docker compose start api`
4. Verify: `curl -fsS localhost:8080/ready` and a sample `/api/predict`

## Still open (GAP)

> **GAP:** No scheduled offsite backups / multi-AZ story.
>
> Next actions: nightly backup artifact upload to object storage; quarterly timed restore drill with recorded RTO.
