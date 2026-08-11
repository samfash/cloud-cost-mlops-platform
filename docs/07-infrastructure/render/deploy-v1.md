---
Status: Implemented (guide)
Owner: You
Last updated: 2026-08-11
Version: 1.0
---

# Deploy v1 on Render — what you must do and provide

This is the **operator checklist for version 1**: cloud-cost + latency inference API (Docker), public HTTPS URL, optional API key. Model-lab (`:8081`) is **not** deployed as a second Render service in v1 (election stays local/CI).

Blueprint file in-repo: [`render.yaml`](../../../render.yaml).

---

## 0. What v1 includes (and does not)

| Included | Not in v1 on Render |
|----------|---------------------|
| Cost RF + latency RF from CAS image | Real cloud-billing ingestion |
| `GET /`, `/estimate`, `/ready`, `/health`, `/metrics` | Separate model-lab service (`:8081`) |
| `POST /api/predict`, `/latency`, batch, async jobs | Prometheus/Grafana stack |
| Optional `API_KEY` + rate limit | Persistent disk for audit DB (ephemeral `/tmp`) |
| TLS via Render | Custom domain (optional — you can add later) |
| Synthetic trained models baked at image build | Multi-region / HPA |

**Honest accuracy caveat:** v1 ships models trained on synthetic `Cloud_Dataset.csv`. Treat predictions as demos until you plug in real CUR/billing data (see [USER_ACTIONS.md](../../USER_ACTIONS.md)).

---

## 1. Accounts and access you must have

1. **GitHub account** with push access to `samfash/cloud-cost-mlops-platform` (this repo already on `main` after the v1 push).
2. **Render account** at [https://dashboard.render.com](https://dashboard.render.com) (GitHub OAuth recommended).
3. Permission to **connect the GitHub repo** to Render (org repos may need admin approve).
4. A password manager or notes file for secrets (`API_KEY`, Render login).

You do **not** need: AWS/GCP/Azure accounts, Kubernetes, MongoDB, Redis, or a custom domain for a working v1.

---

## 2. Choose a Render plan (important for this Dockerfile)

The Dockerfile **trains and packages models during image build**. That makes the **first build slow** (often 10–25+ minutes depending on Render’s network).

| Plan | Notes for v1 |
|------|----------------|
| **Free** (default in `render.yaml`) | Zero cost to try. Service **sleeps** when idle → first request after sleep is slow (cold start). Build timeouts more common on the long train-at-build Dockerfile. |
| **Starter** | Upgrade anytime in Dashboard if Free is too slow/flaky. More reliable builds; less aggressive sleeping. Still a single instance. |
| Higher | Only if you need more RAM/CPU for larger future models. |

**Default path:** deploy on **Free** first. If you like the app and hit sleep/timeouts, upgrade to Starter in **Dashboard → your service → Settings → Plan** (no need to re-Blueprint). Card on file is required only when you upgrade.

If Free **build** times out before the first deploy ever succeeds: upgrade to Starter and redeploy, or later bake artifacts in CI and `COPY` them (not required if Free build finishes).

---

## 3. Secrets and values **you must create / paste into Render**

Set these in **Render Dashboard → your service → Environment** (Blueprint marks `API_KEY` as `sync: false` so you type it in the UI).

### Required for any public URL

| Variable | You provide | Guidance |
|----------|-------------|----------|
| **`API_KEY`** | Yes — generate yourself | Long random string (e.g. `openssl rand -hex 32`). Clients send `X-API-Key: <value>` or `Authorization: Bearer <value>`. **UI pages `/` and `/estimate` stay open** without the key; JSON predict routes require it when set. |

If you leave `API_KEY` empty, the API is **world-writable** for predict — do not do that on a public URL.

### Recommended defaults (Blueprint already sets these; change only if you know why)

| Variable | Default | You change when… |
|----------|---------|------------------|
| `RATE_LIMIT_PER_MINUTE` | `120` | You expect more traffic, or want stricter abuse control |
| `LATENCY_MODEL_ENABLED` | `1` | You want to force clients to always send `latency_ms` |
| `PREDICT_CACHE_ENABLED` | `1` | Debugging cache behavior |
| `PREDICT_CACHE_SIZE` | `1024` | Memory pressure |
| `PREDICT_CACHE_TTL_SECONDS` | `300` | Fresher vs faster repeats |
| `ASYNC_JOBS_ENABLED` | `1` | Disable async batch |
| `AUDIT_LOG_ENABLED` | `1` | Disable SQLite audit |
| `AUDIT_LOG_PATH` | `/tmp/predict_audit.db` | Keep on ephemeral disk (v1) |
| `SERVING_MODE` | `primary` | Later canary/shadow (needs probe pin in CAS) |
| `LOG_LEVEL` | `INFO` | `DEBUG` for a short incident window |

### Injected by Render (do not set manually)

| Variable | Meaning |
|----------|---------|
| **`PORT`** | Render sets this. Image start script binds Gunicorn to `0.0.0.0:$PORT`. |
| `RENDER_*` | Platform metadata — ignore for v1. |

### Not required for v1

- Database URL / Redis / Mongo  
- `MLFLOW_TRACKING_URI`  
- TLS certs (Render terminates HTTPS)  
- Separate model-lab env  

---

## 4. Deploy steps (click-path)

### Option A — Blueprint (preferred)

1. Push `main` with `render.yaml` (done when this guide ships).
2. Render Dashboard → **New** → **Blueprint**.
3. Connect GitHub → select **`cloud-cost-mlops-platform`**.
4. Confirm service **`cloud-cost-api`**, plan **Free** (upgrade to Starter later if you want).
5. When prompted for **`API_KEY`**, paste your generated secret.
6. Apply / create. Wait for **Docker build** (train + package) then deploy.
7. Copy the public URL, e.g. `https://cloud-cost-api.onrender.com`.

### Option B — Manual Docker Web Service

1. **New** → **Web Service** → connect repo.
2. Runtime: **Docker**.
3. Dockerfile path: `./Dockerfile`, context `.`.
4. Health check path: **`/ready`**.
5. Add env vars from section 3 (at least `API_KEY`).
6. Create Web Service → wait for build.

### After deploy — verification **you** run

```bash
BASE=https://YOUR-SERVICE.onrender.com

# Ready (no API key)
curl -fsS "$BASE/ready"

# UI
# open $BASE/ and $BASE/estimate in a browser

# Latency model
curl -fsS -X POST "$BASE/api/predict/latency" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"timestamp":"1/1/2024 0:00","cpu_usage":43.71,"memory_usage":95.56,"net_io":379.4,"disk_io":638.79,"RAM_GB":1,"vCPU":1,"throughput":1380.99,"utilization":69.64,"cloud_provider":"Azure","region":"us-east","vm_type":"t2.micro","target":"scale_up"}'

# Cost (omit latency_ms — model fills)
curl -fsS -X POST "$BASE/api/predict" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"timestamp":"1/1/2024 0:00","cpu_usage":43.71,"memory_usage":95.56,"net_io":379.4,"disk_io":638.79,"RAM_GB":1,"vCPU":1,"throughput":1380.99,"utilization":69.64,"cloud_provider":"Azure","region":"us-east","vm_type":"t2.micro","target":"scale_up"}'
```

Expect: `"status":"success"`, `latency_model_loaded: true` on `/ready` or `/health`.

---

## 5. Operational constraints you must accept for v1

1. **Ephemeral filesystem** — SQLite audit under `/tmp` is wiped on every deploy/restart. Logs go to Render log stream (stdout JSON).
2. **Single instance** — in-process predict cache and async job queue are **not** shared across replicas. Do not scale to N>1 until you add Redis/external queue.
3. **Cold starts (Free)** — first request after sleep can take tens of seconds while the process + models load.
4. **Rebuild = retrain** — changing Dockerfile/deps/dataset triggers a full train during build. Budget time.
5. **No model-lab on Render** — run election locally or in CI only for v1.
6. **Rate limit is per process** — edge DDoS protection is still Render/CDN’s job; `API_KEY` is your app-level control.
7. **Synthetic data** — do not market accuracy as production FinOps truth until real billing lands.

---

## 6. Optional things you may provide later (not blockers for v1)

| Item | Why |
|------|-----|
| Custom domain + DNS | Branding (`api.yourdomain.com`) |
| Render notifications email/Slack | Know when deploys fail |
| GitHub → Render auto-deploy on `main` | Already default if Blueprint connected |
| Persistent disk | Only if you need durable audit DB (mount path + change `AUDIT_LOG_PATH`) |
| Second service for model-lab | Port 8081 sidecar — out of v1 scope |
| Real billing CSV/Parquet + retrain | Accuracy / portfolio credibility |

---

## 7. Checklist summary (print this)

- [ ] GitHub repo connected to Render  
- [ ] Plan **Free** for first deploy (upgrade to Starter later if needed)  
- [ ] Generated and stored **`API_KEY`**  
- [ ] Set `API_KEY` in Render Environment  
- [ ] Deploy finished green; `/ready` returns `ready: true`  
- [ ] Browser: `/` and `/estimate` load  
- [ ] Authenticated curl to `/api/predict` and `/api/predict/latency` succeed  
- [ ] Share URL + API key only with trusted clients  
- [ ] Understand synthetic-data accuracy caveat  

---

## 8. If Blueprint shows **deploy failed**

1. Open the Blueprint → click the failed **`cloud-cost-api`** event (or the service → **Logs** / **Events**).
2. Expand the red deploy and copy the **last ~30 lines** of the build/runtime log (that text is the real error).
3. Common causes on **Free (512 MB)**:
   - **Out of memory** during `pip` / `python main.py` / Gunicorn start → message often `Killed` or `exit code 137`.
   - **Build timeout** / pipeline minutes exhausted.
   - **Health check** `/ready` never becomes 200 (process crash on boot).
4. This repo’s `render.yaml` enables a **slim Free build** (`RENDER_SLIM_BUILD=1`: fewer RF trees, skip model_lab bake, skip pytest). After that commit is synced, use **Manual Sync** on the Blueprint and redeploy.
5. If slim Free still fails: upgrade the service to **Starter** (Settings → Plan) and redeploy — same Dockerfile, more CPU headroom for the build.

## 9. Rollback

Render Dashboard → service → **Deploys** → redeploy previous successful deploy. No DB migration in v1.
