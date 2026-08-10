---
Status: Planned
Owner: You + Platform
Last updated: 2026-08-10
---

# What you need to do (outside this repo)

These items cannot be finished by code alone. Use this as a checklist.

## Data & truth

1. **Connect real billing** (AWS CUR / Azure Cost Export / GCP BigQuery) — replace synthetic `Cloud_Dataset.csv` for credible accuracy.
2. **Online labels** — pipeline that joins predicted cost → actual invoice line items for residual / calibration monitoring.
3. **Human review** of feature dictionary vs your FinOps taxonomy (esp. `target` vs `cost` naming).

## Deploy & security

4. **TLS + edge auth** — terminate HTTPS at nginx/ALB/Cloudflare; set `API_KEY` (or better IdP JWT) in production.
5. **Image registry + CD** — enable GHCR/ECR publish from Actions; add staging environment secrets.
6. **Kubernetes / HPA** (optional) — if Compose is not enough; needs cluster access.

## Observability ops

7. **Alertmanager → Slack/PagerDuty** — wire routes for `CloudCostModelNotLoaded` / 5xx / OOB drift.
8. **Offsite CAS backups** — cron upload of `scripts/backup_cas.sh` tarballs to S3/GCS + restore drill quarterly.
9. **Managed MLflow / W&B** (optional) — set `MLFLOW_TRACKING_URI` to a shared server.

## Product / research (deferred)

10. LLM token pricing, prompt optimization, quality models — only if you expand scope beyond VM cost.
11. Paid competitor teardown / paper library curation — needs subscriptions and analyst time.
12. True online feature store (Feast/Tecton/Vertex) — when multiple services need shared low-latency features.

## Canary rollout (when you have two model versions)

13. Promote a probe via packaging, then:

```bash
export SERVING_MODE=shadow
export CANARY_PERCENT=100
docker compose up -d api
# inspect logs for shadow_score deltas, then:
export SERVING_MODE=canary
export CANARY_PERCENT=10
```
