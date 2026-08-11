---
Status: Planned
Owner: You + Platform
Last updated: 2026-08-11
---

# What you need to do (outside this repo)

These items cannot be finished by code alone. Use this as a checklist.

## Deploy v1 on Render (do this first)

**Full step-by-step + every secret/value you must provide:**

→ **[docs/07-infrastructure/render/deploy-v1.md](07-infrastructure/render/deploy-v1.md)**

Short version:

1. Render account + connect GitHub repo `cloud-cost-mlops-platform`.
2. Deploy Docker Web Service / Blueprint (`render.yaml`) — plan **Starter** recommended (Free may time out on train-at-build).
3. Generate and set **`API_KEY`** in Render Environment (required for public URL).
4. Confirm `/ready`, UI `/` + `/estimate`, and authenticated `/api/predict` + `/api/predict/latency`.
5. Accept v1 limits: ephemeral disk, single instance, synthetic training data, no model-lab service on Render.

Local env template: copy [`.env.example`](../.env.example) → `.env` (never commit real keys).

## Data & truth

1. **Connect real billing** (AWS CUR / Azure Cost Export / GCP BigQuery) — replace synthetic `Cloud_Dataset.csv` for credible accuracy.
2. **Online labels** — pipeline that joins predicted cost → actual invoice line items for residual / calibration monitoring.
3. **Human review** of feature dictionary vs your FinOps taxonomy (esp. `target` vs `cost` naming).

## Deploy & security (beyond Render v1)

4. **TLS + edge auth** — Render already terminates HTTPS; keep `API_KEY` (or later IdP JWT). Optional custom domain in Render.
5. **Image registry + CD** — optional GHCR/ECR; Render can build from Dockerfile on `main`.
6. **Kubernetes / HPA** (optional) — see `deploy/k8s/` if you leave Render.

## Observability ops

7. **Alertmanager → Slack/PagerDuty** — wire routes for `CloudCostModelNotLoaded` / 5xx / OOB drift (Compose `--profile obs` locally; not on Render v1).
8. **Offsite CAS backups** — cron upload of `scripts/backup_cas.sh` tarballs to S3/GCS + restore drill quarterly (local/CI artifacts).
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
