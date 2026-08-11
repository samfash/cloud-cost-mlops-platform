---
Status: Implemented / Partial
Owner: Platform
Last updated: 2026-08-10
---

# System design review (inference-focused)

Hardening checklist against common production concerns. **Monolith first** for this portfolio; split only when load or ownership demands it.

| Topic | Stance here | Status |
|-------|-------------|--------|
| **API design** | Stable JSON contracts; additive fields only (`model_version`, `cache_hit`, `predicted_latency_ms`). Batch + async job poll. OpenAPI under `docs/06-api/`. | Implemented |
| **Authentication** | Optional `API_KEY` (`X-API-Key` / Bearer). Empty = open (local). Set for any public URL. | Partial — no JWT/IdP yet |
| **Caching** | In-process predict cache (TTL/size via env). Lowers repeated-payload latency; single Gunicorn worker keeps coherence. | Implemented |
| **Database indexing** | SQLite predict audit log with indexes on `request_id`, `created_at`, `status`. CAS `catalog.sqlite` for package inventory. | Implemented (local) |
| **Microservices vs monoliths** | One image serves cost + latency models + UI. Separate `model_lab` process only for election. Prefer monolith until fan-out justifies split. | Implemented |
| **Async processing** | `POST /api/predict/batch/async` + `GET /api/jobs/<id>` in-process queue (single worker). Sync batch remains for ≤500. | Implemented |
| **Docker / Kubernetes** | Compose for local/prod-lite; `deploy/k8s/` Deployment + Service + HPA sketch. Non-root image, health/ready probes. | Partial — cluster not wired in CI |
| **Rate limiting** | Per-process sliding window (`RATE_LIMIT_PER_MINUTE`, Compose default **120**). Edge limits still recommended. | Partial |
| **Queues** | In-process job queue (no Redis/SQS yet). Enough for demo + single-node; swap later without changing poll API. | Partial |
| **Observability** | JSON logs, `X-Request-Id`, `/metrics`, Prometheus/Grafana profile, latency-model gauge, audit DB. | Partial — OTel/pager remain |

## Inference latency path

1. Optional request cache → skip model if hit.
2. If `latency_ms` omitted and latency model loaded → RF latency predict (no leakage features).
3. Cost RF predict with filled/provided `latency_ms`.
4. Record wall-clock `latency_ms` in response + Prometheus histogram; optional SQLite audit row.

## Env

See [`.env.example`](../../../.env.example). Copy to `.env` for Compose/Render.
