# Cloud Cost Prediction API

Production ML API that merges training, dependency-aware re-runs, immutable CAS model packaging, and online inference — plus a trial-selection lab for RandomForest election.

## Documentation

Engineering research portfolio (vision, architecture, ML, ADRs, gaps):

- **[docs/README.md](docs/README.md)** — portfolio index & Gap Register

## What's included

| Area | Capability |
|------|------------|
| **Training pipeline** | Validation → transformation → train → evaluate → CAS packaging |
| **Efficient re-runs** | Per-stage Git-blob digests under `artifacts/.pipeline/`; unchanged stages skip |
| **Model packaging** | Immutable content-addressed store (`artifacts/model_bundle/`) with promotion gates |
| **Inference API** | Flask + Gunicorn on **8080** (`/`, `/estimate`, `/health`, `/ready`, `/metrics`, `/predict`, `/api/predict`) |
| **UI** | Non-technical overview at `/` + corporate estimate wizard at `/estimate` |
| **Model lab** | REXX election API on **8081** (`/health`, `/ready`, `/metrics`, `/api/select`) |
| **Observability** | JSON stdout logs, `X-Request-Id`, Prometheus metrics + alert rules; optional Grafana via `docker compose --profile obs` |
| **Caching** | In-process predict cache (TTL/LRU); `cache_hit` on JSON responses |
| **MLOps** | Temporal split, batch predict, drift OOB metrics, MLflow gaps/baseline, canary/shadow hooks, CI metrics gate |
| **API guards** | Optional `API_KEY`; Compose default `RATE_LIMIT_PER_MINUTE=600` |

## Project layout

```
docs/                # engineering research portfolio (vision → ADRs → gaps)
cloud-cost/          # training pipeline + inference API
model_lab/           # trial selector + submission trainer
tests/
  unit/              # fast isolated tests
  integration/       # API smoke, election, idempotency
  legacy_harbor/     # original Harbor verifier suites (not run by default)
scripts/             # train / select helpers
Dockerfile
docker-compose.yml
.github/workflows/ci.yml
```

## Run with Docker (recommended)

### Prerequisites

- [Docker Desktop](https://docs.docker.com/get-docker/) (daemon running) and Docker Compose v2

### Build and start the APIs

```bash
docker compose up --build -d
```

First build trains the model and elects the model-lab submission inside the image (can take several minutes). Later starts reuse the image.

This builds the image (trains + packages the cloud-cost model during the image build), then starts:

- **Inference API** at http://localhost:8080  
- **Model lab API** at http://localhost:8081  

Check readiness (orchestration probe) and metrics:

```bash
curl http://localhost:8080/ready
curl http://localhost:8081/ready
curl http://localhost:8080/metrics | head
# optional Prometheus + Grafana: docker compose --profile obs up -d
#   Prometheus → http://localhost:9090
#   Grafana    → http://localhost:3000
```

### Predict cloud cost

```bash
curl -X POST http://localhost:8080/api/predict \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "1/1/2024 0:00",
    "cpu_usage": 43.71,
    "memory_usage": 95.56,
    "net_io": 379.4,
    "disk_io": 638.79,
    "RAM_GB": 1,
    "vCPU": 1,
    "latency_ms": 228.02,
    "throughput": 1380.99,
    "utilization": 69.64,
    "cloud_provider": "Azure",
    "region": "us-east",
    "vm_type": "t2.micro",
    "target": "scale_up"
  }'
```

Browser UI:

- Overview (non-technical): http://localhost:8080/
- Estimate wizard: http://localhost:8080/estimate

### Elect a model-lab trial

```bash
curl -X POST http://localhost:8081/api/select \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Re-run training inside Docker

```bash
docker compose --profile train run --rm train
```

Unchanged inputs skip stages via dependency ledgers. After training, restart the API to load the new HEAD bundle:

```bash
docker compose up -d api
```

### Run unit tests in Docker

```bash
docker compose --profile test run --rm test
```

### Stop

```bash
docker compose down
```

Persist volumes (model artifacts) across rebuilds with `docker compose down` (without `-v`). Remove volumes with `docker compose down -v`.

## Local development (without Docker)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements-dev.txt

# System dependency for model_lab election:
#   Debian/Ubuntu: sudo apt-get install regina-rexx
#   macOS: brew install regina

export PYTHONPATH="$PWD:$PWD/cloud-cost"

cd cloud-cost && python main.py && cd ..
python -m model_lab.cli

cd cloud-cost && python app.py   # http://localhost:8080
# or: python -m model_lab.app    # http://localhost:8081

pytest tests/unit -q
```

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) runs on push/PR:

1. Unit tests  
2. Full training + packaging smoke  
3. CAS backup/restore drill  
4. Model-lab submission build  
5. API + model-lab integration tests  
6. Docker image build + compose smoke  
7. Observability profile smoke (Prometheus rules)  
8. Trivy image scan (informational)  
9. Ruff lint  

## API reference

### Cloud-cost (`:8080`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Non-technical overview |
| GET | `/estimate` | Cost estimate wizard |
| GET | `/health` | Liveness / model metadata |
| GET | `/ready` | Readiness (503 if model missing) |
| GET | `/metrics` | Prometheus metrics |
| POST | `/predict` | Form-encoded prediction → HTML |
| POST | `/api/predict` | JSON prediction → `prediction` + `status` (+ additive fields) |
| POST | `/api/predict/batch` | Batch JSON instances (≤500) |
| GET | `/ops/model-card` | Offline metrics + serving posture |

### Model lab (`:8081`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health |
| GET | `/ready` | Readiness (trials/constraints/REXX present) |
| GET | `/metrics` | Prometheus metrics |
| POST | `/api/select` | Run REXX election; returns chosen trial JSON |

## Notes

- Packaging refuses dual-metric regressions and seals bundles with `binding_mac` integrity checks.  
- Inference loads **only** from the CAS store HEAD — never from mutable trainer dirs.  
- `params.yaml` invalidates the trainer stage only; packaging-only recovery does not bump lineage when inputs are unchanged.
