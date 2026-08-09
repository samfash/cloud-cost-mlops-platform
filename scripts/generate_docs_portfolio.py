#!/usr/bin/env python3
"""Generate the engineering research portfolio documentation tree under docs/."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DATE = "2026-08-09"


def fm(status: str, owner: str = "Platform") -> str:
    return (
        f"---\n"
        f"Status: {status}\n"
        f"Owner: {owner}\n"
        f"Last updated: {DATE}\n"
        f"---\n\n"
    )


def write(rel: str, body: str) -> None:
    path = DOCS / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.rstrip() + "\n", encoding="utf-8")


def section_readme(title: str, status: str, blurb: str, links: list[tuple[str, str]]) -> str:
    items = "\n".join(f"- [{name}]({href})" for name, href in links)
    return (
        fm(status)
        + f"# {title}\n\n"
        + blurb.strip()
        + "\n\n## Contents\n\n"
        + items
        + "\n"
    )


# ---------------------------------------------------------------------------
# Document bodies
# ---------------------------------------------------------------------------

DOCS_INDEX = fm("Partial") + f"""# Engineering Research Portfolio

Portfolio documentation for the **Cloud Cost Prediction** platform: a FinOps / MLOps system that trains a RandomForest cost model, packages it into an immutable CAS store, serves inference on Flask, and elects RandomForest trials via REXX Borda/Copeland voting.

This tree separates **IMPLEMENTED NOW** from **PLANNED / GAP** so research expansion into LLM cost, latency, and quality intelligence stays honest.

| Field | Value |
|-------|-------|
| Portfolio root | `docs/` |
| Last updated | {DATE} |
| Primary code | `cloud-cost/`, `model_lab/` |
| Inference | `:8080` |
| Model lab | `:8081` |

## Section index

| # | Section | Status | Index |
|---|---------|--------|-------|
| 00 | Vision | Partial | [00-vision](00-vision/README.md) |
| 01 | Research | Partial / Gap | [01-research](01-research/README.md) |
| 02 | Product | Partial | [02-product](02-product/README.md) |
| 03 | Architecture | Implemented / Partial | [03-architecture](03-architecture/README.md) |
| 04 | Machine learning | Implemented + Gap | [04-machine-learning](04-machine-learning/README.md) |
| 05 | Data engineering | Implemented / Partial | [05-data-engineering](05-data-engineering/README.md) |
| 06 | API | Implemented / Gap | [06-api](06-api/README.md) |
| 07 | Infrastructure | Partial / Gap | [07-infrastructure](07-infrastructure/README.md) |
| 08 | Experiments | Partial | [08-experiments](08-experiments/README.md) |
| 09 | Benchmarks | Partial / Gap | [09-benchmarks](09-benchmarks/README.md) |
| 10 | ADRs | Implemented | [10-adrs](10-adrs/README.md) |
| 11 | Risks | Partial | [11-risks](11-risks/risk-register.md) |
| 12 | Weekly reviews | Partial | [12-weekly-reviews](12-weekly-reviews/README.md) |
| 13 | Roadmap | Planned | [13-roadmap](13-roadmap/README.md) |
| — | Assets | Placeholder | [assets](assets/README.md) |

## Implemented system (summary)

- **Model:** `sklearn.ensemble.RandomForestRegressor` predicting VM `cost`
- **Pipeline:** `data_validation` → `data_transformation` → `model_trainer` → `model_evaluation` → CAS `model_packaging`
- **Re-runs:** Git blob SHA-256 digests under `artifacts/.pipeline/`; unchanged stages skip
- **CAS store:** `HEAD`, `pins.json`, `RELEASES`, `catalog.sqlite`, `objects/`, `versions/`
- **APIs:** Flask inference (`/health`, `/predict`, `/api/predict`) on **8080**; model_lab election (`/health`, `/api/select`) on **8081**
- **Ops:** Docker, docker-compose, GitHub Actions CI
- **Holdout (observed):** MAE ≈ 0.00116, RMSE ≈ 0.00182, R² ≈ 0.999 — **caveat:** ~1000-row synthetic `Cloud_Dataset.csv`

```mermaid
flowchart LR
  CSV[Cloud_Dataset.csv] --> DV[data_validation]
  DV --> DT[data_transformation]
  DT --> MT[model_trainer]
  MT --> ME[model_evaluation]
  ME --> CAS[CAS packaging]
  CAS --> API[Flask :8080]
  TRIALS[model_lab trials] --> REXX[REXX election]
  REXX --> LAB[Flask :8081]
```

## Gap Register (top-level)

> Every item below is **not** implemented (or only sketched). See section docs for next actions.

1. LLM token / request pricing intelligence (provider rate cards, cache/discount modeling)
2. Tokenization cost attribution and prompt→token estimators
3. Latency-prediction model (p50/p95/p99) beyond raw feature `latency_ms`
4. Quality / usefulness prediction for LLM responses
5. Recommendation engine for VM / region / model routing
6. Prompt optimization loop (auto rewrite / few-shot selection)
7. Production OpenAPI codegen + typed SDKs (Python/TS)
8. Outbound webhooks / event bus for publish & election events
9. Paid competitor teardown with primary-source pricing data
10. Production observability stack (Prometheus/OTel, dashboards, SLOs)
11. Alerting routes (PagerDuty/Slack) with runbook links
12. Disaster-recovery runbooks with proven RTO/RPO drills
13. Real FinOps CUR/BigQuery billing ingestion (vs synthetic CSV)
14. AuthN/AuthZ, rate limiting, and multi-tenant isolation on APIs
15. Online feature store + training/serving skew monitors
16. Model monitoring / drift detection in production
17. Multi-model serving (canary, shadow, A/B) beyond HEAD pin
18. Horizontal autoscaling / K8s manifests (compose-only today)
19. Formal threat-model review with residual risk sign-off
20. Public paper / blog artifacts and external references curation completeness

## How to read status labels

| Status | Meaning |
|--------|---------|
| **Implemented** | Code + artifacts exist and are exercised by CI or local runs |
| **Partial** | Some pieces exist; gaps called out inline |
| **Planned** | Intentionally designed, not built |
| **Gap** | Research or product hole; needs next actions |

## Related code docs

- [`cloud-cost/docs/model_bundle_contract.md`](../cloud-cost/docs/model_bundle_contract.md) — CAS packaging contract
"""

VISION = fm("Partial") + """# Vision

## North star

Build a **cloud cost intelligence platform** that turns telemetry and catalog signals into trustworthy cost predictions, sealed model artifacts, and selectable training candidates — then expand the same MLOps spine into **LLM cost, latency, and quality** intelligence for FinOps teams.

## Implemented now

- End-to-end VM cost regression (RandomForest) with dependency-aware pipeline re-runs
- Immutable CAS model packaging with promotion gates and integrity seals
- Online inference API and HTML form on `:8080`
- Model-lab REXX Borda/Copeland election API on `:8081`
- Docker Compose + GitHub Actions CI smoke path

## Planned expansion

| Horizon | Theme |
|---------|-------|
| Near | Auth, observability, real billing data ingestion |
| Mid | Latency & quality models; provider rate-card FinOps |
| Far | LLM prompt optimization, routing recommendations, multi-tenant SaaS |

## Non-goals (current phase)

- Replacing cloud provider billing systems
- Guaranteeing dollar-accurate forecasts on synthetic data
- Shipping LLM inference itself (we predict/manage cost of workloads, not host models)

> **GAP:** Product positioning vs commercial FinOps suites (CloudHealth, Apptio, Kubecost, CloudZero) is research-only. Next: publish a one-page competitive thesis with primary citations.
"""

# --- 01 research ---

RESEARCH_INDUSTRY = fm("Partial") + """# Industry landscape — FinOps & cloud cost ML

## Context

Enterprises treat cloud spend as a managed financial practice (**FinOps**). Predictive cost models sit beside allocation, anomaly detection, and rightsizing. MLOps practices (immutable artifacts, promotion gates, lineage) are increasingly required when models influence spend decisions.

## Implemented alignment

This portfolio implements a **training → seal → serve** spine suitable for cost regression, with digest-based skip logic for cheap iteration — patterns common in industrial ML platforms.

## Industry themes (research)

1. **Unit economics:** cost per request, per vCPU-hour, per token
2. **Showback / chargeback:** attributing spend to teams and products
3. **Anomaly detection:** sudden spend spikes vs forecast
4. **Rightsizing:** recommending cheaper SKUs for the same SLO
5. **LLM FinOps:** token pricing, caching, batching, model routing

> **GAP:** No primary market-sizing study or customer interviews in-repo. Next actions: (1) interview 3 FinOps practitioners, (2) summarize TAM/SAM from public analyst notes, (3) map our CAS + election pattern to MLOps maturity models.
"""

RESEARCH_COMPETITORS = fm("Gap") + """# Competitor notes

## Positioning matrix (desk research — unverified pricing)

| Player | Focus | Overlap with us |
|--------|-------|-----------------|
| Kubecost / OpenCost | K8s cost allocation | Allocation, not RF regression |
| CloudZero | Cost intelligence | Strong FinOps UX |
| Apptio Cloudability | Enterprise FinOps | Mature reporting |
| AWS Cost Explorer / Azure Cost Mgmt | Native billing | Source of truth data |
| Evidently / WhyLabs | ML monitoring | Complementary gap |

## Implemented differentiator (real)

- Content-addressed model packaging with promotion gates and `binding_mac`
- Git-blob dependency digests for stage skip
- REXX social-choice election over RandomForest trial grids

> **GAP:** No paid competitor teardown, no primary-source pricing tables, no feature parity spreadsheet with dates. Next actions: (1) build a 10-row parity matrix from public docs only, (2) mark every cell Source/Date, (3) avoid inventing ARR or customer counts.
"""

RESEARCH_LLM_PRICING = fm("Gap") + """# LLM pricing research

## Why it matters

LLM spend is driven by **tokens in/out**, model tier, caching, batch APIs, and region. A future platform capability would ingest rate cards and predict $ / request.

## Implemented now

**None.** Current model predicts synthetic VM `cost` from infrastructure features, not LLM bills.

> **GAP:** LLM pricing intelligence absent. Next actions:
> 1. Ingest public OpenAI/Anthropic/Google rate cards as versioned YAML
> 2. Define schema: `provider, model, unit, input_price, output_price, cache_price, effective_date`
> 3. Prototype calculator endpoint separate from RF VM cost model
> 4. Document currency and tax assumptions
"""

RESEARCH_TOKENIZATION = fm("Gap") + """# Tokenization & cost attribution

## Concept

Token counts mediate between prompts and dollars. Estimators (tiktoken, SentencePiece approximations) enable pre-flight cost checks.

## Implemented now

**None.** Dataset has no prompt/token fields.

> **GAP:** No tokenizer integration or prompt→token estimator. Next actions:
> 1. Add optional `prompt_text` feature path (planned API)
> 2. Benchmark tiktoken vs vendor billed tokens on a golden set
> 3. Store attribution: `tokens_in, tokens_out, cached_tokens, usd`
"""

RESEARCH_LLMOPS = fm("Partial") + """# LLMOps / MLOps notes

## Implemented MLOps patterns (this repo)

| Pattern | Where |
|---------|-------|
| Stage graph + validators | `stage_definitions.py` |
| Content digests / skip | `dependency_tracker.py`, `artifacts/.pipeline/` |
| Immutable publish | `model_packager.py`, CAS store |
| CI smoke train+serve | `.github/workflows/ci.yml` |
| Trial election | `model_lab` + Regina REXX |

## Planned LLMOps extensions

- Prompt/version registries
- Eval harnesses for quality + cost jointly
- Shadow traffic for routing policies

> **GAP:** No prompt registry, no LLM eval harness, no online drift monitors. Next: specify an `evals/` layout and metrics contract before coding.
"""

RESEARCH_FINOPS = fm("Partial") + """# FinOps research notes

## Principles we already support

1. **Traceability:** CAS digests and RELEASES ledger
2. **Change control:** promotion gates (R² / MAE / schema)
3. **Operational efficiency:** dependency skip digests

## Principles not yet supported

- Real CUR / export ingestion
- Allocation tags and shared-cost splitting
- Budget alerts and anomaly detection on live spend

> **GAP:** Synthetic CSV only — not linked to billing accounts. Next actions: define a `BillingEvent` schema; spike AWS CUR → Parquet loader offline.
"""

RESEARCH_PAPERS = fm("Gap") + """# Papers & reading list

Curated starters (not endorsements; verify PDFs yourself):

| Topic | Suggested search keys |
|-------|----------------------|
| FinOps | FinOps Foundation Framework |
| Cost forecasting | cloud cost prediction random forest / time series |
| Social choice | Borda count, Copeland method |
| Content-addressed storage | Git object model, CAS |
| LLM pricing | token economics, inference cost modeling |

> **GAP:** No annotated bibliography with DOIs stored in-repo. Next: add 8–12 citations with 2–3 sentence notes each under `references/`.
"""

RESEARCH_REFERENCES = fm("Gap") + """# References

## Internal (implemented)

- Root `README.md`
- `cloud-cost/docs/model_bundle_contract.md`
- `cloud-cost/params.yaml`, `schema.yaml`, `config/config.yaml`
- ADRs under `docs/10-adrs/`

## External

> **GAP:** External reference list incomplete. Next actions:
> 1. FinOps Foundation Framework (link + version)
> 2. scikit-learn RandomForestRegressor docs (version pin)
> 3. Regina REXX documentation
> 4. OpenAPI 3.1 specification
> 5. OWASP API Security Top 10
"""

# --- 02 product ---

PRD = fm("Partial") + """# PRD — Cloud Cost Prediction Platform

## Problem

Teams need a reproducible way to train, seal, and serve VM cost predictions without ad-hoc pickle folders or silent metric regressions.

## Goals (implemented)

1. Train RF regressor on `Cloud_Dataset.csv`
2. Skip unchanged pipeline stages via Git-blob digests
3. Publish only through CAS gates
4. Serve predictions on Flask `:8080`
5. Elect model-lab trials via REXX on `:8081`

## Non-goals

- Dollar-accurate forecasts on production billing (dataset is synthetic)
- Multi-tenant SaaS in v1
- LLM token billing (planned)

## Success metrics

| Metric | Target | Observed |
|--------|--------|----------|
| Holdout R² | ≥ 0.95 (lab) | ~0.999 |
| Holdout MAE | low on scale of `cost` | ~0.00116 |
| CI green | required | unit + train smoke + docker build |
| Stage skip correctness | digests stable | covered by unit/integration tests |

> **Caveat:** Near-perfect metrics reflect a small synthetic dataset; do not claim production accuracy.

## Requirements

### Functional (done)

- Predict `cost` from VM/telemetry features
- Health endpoint exposes bundle version + metrics
- Packaging refuses dual-metric regressions per contract

### Functional (planned)

- AuthN/AuthZ, webhooks, SDKs, LLM cost modules

> **GAP:** No signed-off PRD with stakeholders. Next: ratify goals/non-goals with course/advisor or product owner.
"""

PERSONAS = fm("Partial") + """# Personas

## 1. ML Platform Engineer (primary — implemented workflows)

Needs reproducible training, sealed artifacts, CI. Uses `python main.py`, Compose, CAS HEAD.

## 2. FinOps Analyst (secondary — partial)

Wants cost predictions and scenario comparison. Today: HTML form + JSON API only; no dashboards.

## 3. App Developer (planned)

Wants SDK + predictable latency for `/api/predict`.

## 4. LLM Platform Owner (future / gap)

Needs token cost, latency, quality trade-offs — **not implemented**.

> **GAP:** Personas are desk-authored, not interview-backed. Next: validate with 2–3 users.
"""

USER_STORIES = fm("Partial") + """# User stories

## Implemented

1. As an ML engineer, I can run the full pipeline and get a sealed CAS version so inference never loads a mutable trainer pickle.
2. As an ML engineer, I can re-run training after a params-only change and skip validation/transform when digests match.
3. As an API consumer, I can `POST /api/predict` and receive `{"prediction": float, "status": "success"}`.
4. As a researcher, I can `POST /api/select` on model_lab to elect a trial via Borda/Copeland.

## Planned / Gap

5. As a FinOps analyst, I can compare predicted vs actual cloud invoice lines.  
   > **GAP:** No billing ingestion.
6. As a developer, I can install an official Python SDK.  
   > **GAP:** No SDK package.
7. As an LLM owner, I can estimate token USD before calling a model.  
   > **GAP:** No LLM pricing module.
"""

PRODUCT_ROADMAP = fm("Planned") + """# Product roadmap (portfolio)

| Phase | Theme | Status |
|-------|-------|--------|
| P0 | Train / package / serve VM cost | **Implemented** |
| P1 | Auth, observability, real data connectors | Planned |
| P2 | Latency + quality models | Gap |
| P3 | LLM pricing + prompt optimization | Gap |
| P4 | Recommendations & multi-model routing | Gap |

See also [13-roadmap](../13-roadmap/README.md).
"""

FEATURE_PRIO = fm("Partial") + """# Feature prioritization

## Now (keep hardening)

1. CAS contract compliance & tests
2. Dependency digest correctness
3. API smoke + Docker reliability
4. Documentation honesty (this portfolio)

## Next (P1)

1. API auth + rate limits
2. Structured logging / metrics export
3. Real billing sample connector (read-only)

## Later

1. Latency/quality models
2. LLM rate cards + tokenization
3. Webhooks + SDKs
4. K8s deployment

Scoring heuristic: **Impact × Confidence / Effort**, with veto if it obscures Implemented vs Gap.
"""

# --- 03 architecture ---

ARCH_CONTEXT = fm("Implemented") + """# System context

```mermaid
C4Context
  title Cloud Cost Prediction — Context
  Person(eng, "ML Engineer", "Trains and packages models")
  Person(client, "API Client", "Requests cost predictions")
  System(ccp, "Cloud Cost Prediction", "RF training, CAS, Flask APIs")
  System_Ext(docker, "Docker Host", "Runs compose stack")
  System_Ext(gha, "GitHub Actions", "CI")
  Rel(eng, ccp, "Runs pipeline / elects trials")
  Rel(client, ccp, "HTTP predict / health")
  Rel(ccp, docker, "Containers")
  Rel(gha, ccp, "Build & test")
```

## External actors

| Actor | Interaction |
|-------|-------------|
| ML Engineer | `main.py`, model_lab CLI, Compose train profile |
| API Client | HTTP JSON / form posts |
| CI | Checkout, pytest, train smoke, docker build |

No cloud billing APIs are integrated yet.
"""

ARCH_CONTAINERS = fm("Implemented") + """# Containers

```mermaid
flowchart TB
  subgraph compose [docker-compose]
    API[api :8080<br/>Gunicorn/Flask cloud-cost]
    LAB[model-lab :8081<br/>Flask model_lab]
    TRAIN[train profile<br/>python main.py]
    TEST[test profile<br/>pytest unit]
    VOL[(model-artifacts volume)]
  end
  API --> VOL
  TRAIN --> VOL
  LAB --> API
```

| Service | Image | Ports | Role |
|---------|-------|-------|------|
| `api` | `cloud-cost-api:latest` | 8080 | Inference from CAS HEAD |
| `model-lab` | same image | 8081 | Trial election |
| `train` | profile | — | Re-train into volume |
| `test` | profile | — | Unit tests |
"""

ARCH_COMPONENTS = fm("Implemented") + """# Components

## cloud-cost

| Component | Responsibility |
|-----------|----------------|
| `data_validation` | Schema/status checks on CSV |
| `data_transformation` | Encoders, feature eng, train/test split |
| `model_trainer` | Fit RandomForest from `params.yaml` |
| `model_evaluation` | Holdout MAE/MSE/RMSE/R² |
| `model_packager` | CAS publish + gates |
| `PredictionPipeline` | Load HEAD bundle, predict |
| `dependency_tracker` | Git-blob digests / skip |

## model_lab

| Component | Responsibility |
|-----------|----------------|
| `selector` / REXX | Borda & Copeland election |
| `cli` | Build submission offline |
| Flask `app` | `/api/select` |
"""

ARCH_DEPLOYMENT = fm("Partial") + """# Deployment view

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
"""

ARCH_SEQUENCE = fm("Implemented") + """# Sequence — prediction

```mermaid
sequenceDiagram
  participant C as Client
  participant A as Flask :8080
  participant P as PredictionPipeline
  participant CAS as model_bundle HEAD
  C->>A: POST /api/predict JSON
  A->>P: CustomData + predict
  P->>CAS: Load sealed artifacts (startup)
  P-->>A: yhat cost
  A-->>C: {"prediction": float, "status": "success"}
```

## Sequence — packaging (happy path)

```mermaid
sequenceDiagram
  participant E as PipelineExecutor
  participant T as Trainer
  participant Ev as Evaluator
  participant M as ModelPackager
  participant S as CAS store
  E->>T: train if digest miss
  E->>Ev: evaluate holdout
  E->>M: package candidate
  M->>M: gates vs parent
  M->>S: objects + versions + HEAD
```
"""

ARCH_DATAFLOW = fm("Implemented") + """# Data flow

```mermaid
flowchart TD
  RAW[dataset/Cloud_Dataset.csv] --> V[status.txt]
  RAW --> FE[feature engineering]
  FE --> TR[train.csv / test.csv]
  FE --> ENC[label_encoders.pkl]
  FE --> FC[feature_columns.json]
  TR --> RF[model.pkl]
  RF --> MET[metrics.json]
  RF --> CAS[objects/ + versions/]
  ENC --> CAS
  FC --> CAS
  MET --> CAS
  CAS --> INF[Inference API]
```

Digests of inputs/code land in `artifacts/.pipeline/<stage>.json` to decide skip vs re-run.
"""

ARCH_ERD = fm("Partial") + """# Logical data model / ERD

```mermaid
erDiagram
  DATASET_ROW ||--o{ FEATURE_ROW : transforms_to
  FEATURE_ROW ||--|| TRAIN_SPLIT : partitioned
  MODEL_VERSION ||--|{ CAS_BLOB : references
  MODEL_VERSION ||--|| METRICS : reports
  MODEL_VERSION ||--o| PIN : may_be
  HEAD ||--|| MODEL_VERSION : points_to
  CATALOG ||--|{ CAS_BLOB : indexes

  DATASET_ROW {
    string timestamp
    float cpu_usage
    float cost
  }
  MODEL_VERSION {
    string semver
    string promotion_class
    string binding_mac
  }
  CAS_BLOB {
    string sha256
    int size
  }
  METRICS {
    float MAE
    float RMSE
    float R2
  }
```

`catalog.sqlite` is rebuilt on each successful publish (WAL). Not a long-lived OLTP schema for product data.

> **GAP:** No persistent product DB for users, API keys, or billing events.
"""

ARCH_THREAT = fm("Gap") + """# Threat model (draft)

## Assets

- Sealed model blobs and HEAD pointer
- Inference API availability
- Training dataset integrity

## STRIDE sketch

| Threat | Example | Mitigations today | Residual |
|--------|---------|-------------------|----------|
| Tampering | Swap `model.pkl` | CAS digests, binding_mac | Local FS still writable by host |
| Spoofing | Fake client | **None** (no auth) | High |
| Info disclosure | Feature schema leakage | Minimal | Medium |
| DoS | Flood `/api/predict` | **None** | High |
| Elevation | Write HEAD as non-pipeline user | OS perms only | Medium |

> **GAP:** No formal review, no auth, no rate limit, no signed provenance from CI to prod. Next actions: (1) add API key middleware, (2) document trust boundary diagram, (3) schedule lightweight threat review.
"""

ARCH_CACHING = fm("Partial") + """# Caching

## Implemented

- Pipeline stage skip via content digests (compute cache)
- Docker image layers
- Compose volume reuse for artifacts

## Not implemented

- HTTP response cache for predictions
- Feature/result Redis cache
- CDN

> **GAP:** No prediction cache layer. Next: measure p95 latency; only add cache if idempotent GETs are introduced (today predict is POST).
"""

ARCH_SCALABILITY = fm("Gap") + """# Scalability

## Current posture

Single Compose stack, one API process model (Gunicorn in container as packaged). RF inference is CPU-bound and cheap per row for this feature width.

## Limits

- No horizontal pod autoscaling
- CAS on local volume — not shared object storage
- Training inside image build couples build time to data size

> **GAP:** No load test results or HPA configs. Next: k6 script against `/api/predict`; define RPS budget.
"""

ARCH_SECURITY = fm("Partial") + """# Security notes

## Implemented

- Packaging integrity (`binding_mac`, digest ring, seal tag)
- Inference loads only CAS HEAD (not trainer dir)
- CI lint (ruff) + tests

## Missing controls

- TLS termination config in Compose
- Authentication / authorization
- Secrets management
- Dependency scanning gate (beyond what GH may provide by default)
- SBOM publication

> **GAP:** APIs are open on localhost ports by default. Next: document network exposure; add optional `API_TOKEN` check.
"""

ARCH_DECISIONS = fm("Implemented") + """# Architecture decisions index

Canonical ADRs live in [`docs/10-adrs/`](../10-adrs/README.md):

- [ADR-0001](../10-adrs/ADR-0001-cas-packaging.md) — CAS packaging
- [ADR-0002](../10-adrs/ADR-0002-dependency-digests.md) — Dependency digests
- [ADR-0003](../10-adrs/ADR-0003-flask-vs-fastapi.md) — Flask vs FastAPI
- [ADR-0004](../10-adrs/ADR-0004-rexx-election.md) — REXX election
"""

# --- 04 ML ---

ML_COST = fm("Implemented") + """# Cost prediction (IMPLEMENTED)

## Objective

Regress continuous VM **`cost`** from utilization, sizing, and categorical cloud features.

## Algorithm

`sklearn.ensemble.RandomForestRegressor` with params from `cloud-cost/params.yaml`:

| Param | Value |
|-------|-------|
| n_estimators | 300 |
| max_depth | 20 |
| min_samples_split | 5 |
| min_samples_leaf | 2 |
| max_features | sqrt |
| random_state | 42 |

## Observed holdout metrics

From `artifacts/model_evaluation/metrics.json` (representative run):

| Metric | Value |
|--------|-------|
| MAE | ≈ 0.00115786 |
| MSE | ≈ 3.31e-6 |
| RMSE | ≈ 0.00181872 |
| R² | ≈ 0.998964 |

> **Caveat:** ~1000-row synthetic dataset — metrics are optimistic and not proof of production accuracy.

## Serving

`PredictionPipeline` loads sealed bundle from CAS HEAD; Flask exposes `/api/predict`.
"""

ML_LATENCY = fm("Gap") + """# Latency prediction

## Intent

Predict service or LLM latency percentiles (p50/p95/p99) for SLO-aware routing.

## Implemented now

`latency_ms` is an **input feature** to the cost model, not a prediction target. No latency model exists.

> **GAP:** Latency-prediction model absent. Next actions:
> 1. Define target (`latency_p95`) and label source
> 2. Choose model class (RF / GBDT / quantile regression)
> 3. Add evaluation suite separate from cost metrics
> 4. Keep CAS packaging contract reusable
"""

ML_QUALITY = fm("Gap") + """# Quality prediction

## Intent

Score LLM or service response quality (usefulness, toxicity proxies, task success).

## Implemented now

**None.**

> **GAP:** Quality-prediction stack absent. Next actions:
> 1. Pick label protocol (human / LLM-as-judge — disclose bias)
> 2. Store eval datasets under version control or CAS
> 3. Multi-objective election criteria in model_lab later
"""

ML_RECOMMENDATION = fm("Gap") + """# Recommendation

## Intent

Recommend VM type / region / model tier under cost and latency constraints.

## Implemented now

Model-lab **elects training trials**, not user-facing SKU recommendations.

> **GAP:** No recommendation API for cloud SKUs or LLM routes. Next: define constraint language reuse from `constraints.yaml` for SKUs.
"""

ML_PROMPT = fm("Gap") + """# Prompt optimization

## Intent

Automatically rewrite prompts to reduce tokens while holding quality.

## Implemented now

**None.**

> **GAP:** Prompt optimization loop absent. Next actions:
> 1. Offline rewrite candidates + eval harness
> 2. Track token delta and quality delta
> 3. Only then expose an API
"""

# --- 05 data ---

DATA_SCHEMAS = fm("Implemented") + """# Schemas

## Source dataset

Path: `cloud-cost/dataset/Cloud_Dataset.csv` (~1000 rows).  
Validated via `schema.yaml` + data_validation stage.

## Feature schema (packaged)

`feature_columns.json` records `feature_order` (25 features) and `n_features`. Schema breaks affect CAS promotion class.

## Example raw fields

`timestamp`, `cpu_usage`, `memory_usage`, `net_io`, `disk_io`, `cloud_provider`, `region`, `vm_type`, `vCPU`, `RAM_GB`, `price_per_hour`, `target`, `latency_ms`, `throughput`, `utilization`, **`cost`** (label).
"""

DATA_PIPELINES = fm("Implemented") + """# Pipelines

Stage graph (see `stage_definitions.py`):

1. **data_validation** — CSV + schema → `status.txt`
2. **data_transformation** — features, encoders, train/test
3. **model_trainer** — RF fit → `model.pkl`
4. **model_evaluation** — holdout metrics JSON
5. **model_packaging** — CAS publish

Dependency ledgers: `artifacts/.pipeline/<stage_id>.json`.
"""

DATA_ETL = fm("Partial") + """# ETL

## Implemented

In-process Python transforms (pandas) from local CSV — not a distributed ETL grid.

## Planned

Billing export ETL (CUR → Parquet → feature tables).

> **GAP:** No Airflow/Dagster/Spark jobs. Next: keep CSV path; add optional Parquet reader interface.
"""

DATA_FE = fm("Implemented") + """# Feature engineering

Implemented in `src/utils/feature_engineering.py` and transformation stage.

## Engineered signals (packaged order includes)

- Time parts: `hour`, `day`, `month`, `day_of_week`, `is_weekend`
- Encodings: provider, region, vm_type, target
- Ratios/aggregates: `cpu_memory_ratio`, `total_io`, `io_ratio`, `resource_efficiency`, `latency_throughput_ratio`, `resource_intensity`, `ram_per_vcpu`

Label encoders persisted for serving parity.
"""

DATA_QUALITY = fm("Partial") + """# Data quality

## Implemented

- Validation stage writes status
- Output validators (CSV has `cost`, pickle loadable, metrics keys present)
- Packaging refuses missing metric keys / floor-ceiling breaches

## Missing

- Great Expectations / Deequ suites
- Drift detection vs training distribution
- PII classification (synthetic today)

> **GAP:** No continuous DQ monitors in production. Next: add simple PSI on numeric features at predict time (log-only).
"""

DATA_DICT = fm("Implemented") + """# Data dictionary (core fields)

| Field | Role | Notes |
|-------|------|-------|
| timestamp | raw | Parsed into calendar features |
| cpu_usage | feature | Utilization signal |
| memory_usage | feature | Utilization signal |
| net_io / disk_io | feature | IO intensity |
| cloud_provider | categorical | Encoded |
| region | categorical | Encoded |
| vm_type | categorical | Encoded |
| vCPU / RAM_GB | feature | Size |
| price_per_hour | raw/aux | Present in dataset; confirm training usage in transform |
| target | categorical | e.g. scale_up; encoded |
| latency_ms | feature | Not prediction target |
| throughput | feature | |
| utilization | feature | |
| cost | **label** | Regression target |

Synthetic data — treat as lab fixture, not invoice truth.
"""

# --- 06 API ---

API_ENDPOINTS = fm("Implemented") + """# Endpoints

## Cloud-cost `:8080`

| Method | Path | Body | Response |
|--------|------|------|----------|
| GET | `/` | — | HTML form |
| GET | `/health` | — | JSON model/bundle status |
| POST | `/predict` | form-encoded | HTML results |
| POST | `/api/predict` | JSON features | `prediction`, `status` |

## Model lab `:8081`

| Method | Path | Body | Response |
|--------|------|------|----------|
| GET | `/health` | — | `status`, `service` |
| POST | `/api/select` | optional paths JSON | `chosen` trial |

See [openapi/openapi.yaml](openapi/openapi.yaml).
"""

API_WEBHOOKS = fm("Gap") + """# Webhooks

## Intent

Notify subscribers when CAS HEAD changes or a trial is elected.

## Implemented now

**None.**

> **GAP:** No webhook dispatcher, signatures, or retry policy. Next actions:
> 1. Define events: `model.published`, `model.refused`, `trial.selected`
> 2. HMAC-signed POST with exponential backoff
> 3. Delivery log table
"""

API_SDKS = fm("Gap") + """# SDKs

## Implemented now

Raw HTTP (curl / fetch). No published client packages.

> **GAP:** No Python/TypeScript SDKs or OpenAPI codegen pipeline. Next:
> 1. Freeze `openapi.yaml`
> 2. Generate `cloudcost-client` with httpx
> 3. Publish under private index or monorepo `/sdk`
"""

OPENAPI_YAML = """openapi: 3.1.0
info:
  title: Cloud Cost Prediction & Model Lab APIs
  version: 1.0.0
  description: |
    OpenAPI-ish description of the **implemented** Flask services.
    Inference (:8080) predicts VM cost from a sealed CAS RandomForest bundle.
    Model lab (:8081) elects RandomForest trials via REXX Borda/Copeland.
  contact:
    name: Platform
x-portfolio-status: Implemented
x-last-updated: 2026-08-09
servers:
  - url: http://localhost:8080
    description: Cloud-cost inference
  - url: http://localhost:8081
    description: Model lab election
tags:
  - name: inference
  - name: model-lab
paths:
  /:
    get:
      tags: [inference]
      summary: HTML prediction form
      servers:
        - url: http://localhost:8080
      responses:
        "200":
          description: HTML UI
          content:
            text/html:
              schema:
                type: string
  /health:
    get:
      tags: [inference]
      summary: Inference health and bundle metadata
      servers:
        - url: http://localhost:8080
      responses:
        "200":
          description: Health payload
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/InferenceHealth"
    # model-lab also exposes GET /health on :8081
  /predict:
    post:
      tags: [inference]
      summary: Form-encoded prediction returning HTML
      servers:
        - url: http://localhost:8080
      requestBody:
        required: true
        content:
          application/x-www-form-urlencoded:
            schema:
              $ref: "#/components/schemas/PredictFeatures"
      responses:
        "200":
          description: HTML results page
        "500":
          description: Model unavailable or prediction error
  /api/predict:
    post:
      tags: [inference]
      summary: JSON prediction
      servers:
        - url: http://localhost:8080
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/PredictFeatures"
            example:
              timestamp: "1/1/2024 0:00"
              cpu_usage: 43.71
              memory_usage: 95.56
              net_io: 379.4
              disk_io: 638.79
              RAM_GB: 1
              vCPU: 1
              latency_ms: 228.02
              throughput: 1380.99
              utilization: 69.64
              cloud_provider: Azure
              region: us-east
              vm_type: t2.micro
              target: scale_up
      responses:
        "200":
          description: Prediction result
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/PredictResponse"
        "500":
          description: Error
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Error"
  /api/select:
    post:
      tags: [model-lab]
      summary: Elect a trial via REXX Borda/Copeland
      servers:
        - url: http://localhost:8081
      requestBody:
        required: false
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/SelectRequest"
      responses:
        "200":
          description: Chosen trial
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/SelectResponse"
components:
  schemas:
    PredictFeatures:
      type: object
      required:
        - timestamp
        - cpu_usage
        - memory_usage
        - net_io
        - disk_io
        - RAM_GB
        - vCPU
        - latency_ms
        - throughput
        - utilization
        - cloud_provider
        - region
        - vm_type
        - target
      properties:
        timestamp:
          type: string
          example: "1/1/2024 0:00"
        cpu_usage:
          type: number
        memory_usage:
          type: number
        net_io:
          type: number
        disk_io:
          type: number
        RAM_GB:
          type: number
        vCPU:
          type: number
        latency_ms:
          type: number
        throughput:
          type: number
        utilization:
          type: number
        cloud_provider:
          type: string
        region:
          type: string
        vm_type:
          type: string
        target:
          type: string
          description: Operational target label (e.g. scale_up)
        price_per_hour:
          type: number
          description: Optional depending on transform expectations
    PredictResponse:
      type: object
      properties:
        prediction:
          type: number
          description: Predicted VM cost
        status:
          type: string
          example: success
    InferenceHealth:
      type: object
      properties:
        model_loaded:
          type: boolean
        bundle_dir:
          type: string
          nullable: true
        model_version:
          type: string
          nullable: true
        bundle_exists:
          type: boolean
        bundle_files:
          type: array
          items:
            type: string
        metrics:
          type: object
          additionalProperties:
            type: number
    SelectRequest:
      type: object
      properties:
        trials_dir:
          type: string
          description: Optional override path to trials
        constraints_path:
          type: string
          description: Optional override path to constraints YAML
    SelectResponse:
      type: object
      properties:
        status:
          type: string
          example: success
        chosen:
          type: object
          additionalProperties: true
    Error:
      type: object
      properties:
        error:
          type: string
"""

# --- 07 infra ---

INFRA_DEPLOY = fm("Partial") + """# Deployment

## Implemented

```bash
docker compose up --build -d
docker compose --profile train run --rm train
docker compose --profile test run --rm test
```

- Image: `cloud-cost-api:latest`
- Volume: `model-artifacts` → `/app/cloud-cost/artifacts`

## Gap

> **GAP:** No cloud deploy runbook (ECS/EKS/Cloud Run). Next: pick one target and write a 1-page deploy checklist.
"""

INFRA_CICD = fm("Implemented") + """# CI/CD

GitHub Actions `.github/workflows/ci.yml`:

```mermaid
flowchart LR
  A[checkout] --> B[unit tests]
  B --> C[train + package smoke]
  C --> D[model_lab CLI]
  D --> E[API smoke]
  E --> F[docker build]
  A --> G[ruff lint]
```

Triggers: push to `main`/`master`, pull requests. Python 3.13, installs `regina-rexx`.

No CD promotion to a hosted environment yet.
"""

INFRA_OBS = fm("Gap") + """# Observability

> **GAP:** No Prometheus, OpenTelemetry, or Grafana stack. App uses module logging only. Next actions:
> 1. Emit structured JSON logs
> 2. Expose `/metrics` (Prometheus)
> 3. Trace predict path with OTel
"""

INFRA_LOGGING = fm("Partial") + """# Logging

## Implemented

`src/logging/logger` used by Flask app and pipeline components (file/console style per project setup).

## Gap

> **GAP:** No centralized log aggregation (ELK/Loki). Next: document log fields (`request_id`, `model_version`, `mae` on health).
"""

INFRA_MON = fm("Gap") + """# Monitoring

> **GAP:** No SLO dashboards or uptime checks beyond Compose healthcheck. Next:
> 1. Define SLOs (availability, predict latency)
> 2. Synthetic check on `/health` every 1m
> 3. Track model_version changes as events
"""

INFRA_ALERTS = fm("Gap") + """# Alerts

> **GAP:** No PagerDuty/Slack alert routes. Next: alert on healthcheck fail, packaging refuse spikes, and CI red on main.
"""

INFRA_DR = fm("Gap") + """# Disaster recovery

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
"""

# --- 08 experiments ---

def experiment_week(n: int, title: str, status: str, body: str) -> str:
    return fm(status) + f"# Week {n:02d} — {title}\n\n" + body.strip() + "\n"

EXP1 = experiment_week(
    1,
    "Baseline pipeline & dataset",
    "Implemented",
    """
## Hypothesis

A RandomForest on engineered VM features can fit synthetic cloud cost with high holdout R².

## Work

- Wired validation → transform → train → evaluate
- Locked params (`n_estimators=300`, `max_depth=20`, …)
- Established `Cloud_Dataset.csv` as fixture

## Result

Holdout R² ≈ 0.999, MAE ≈ 0.00116 — flagged as synthetic optimism.
""",
)

EXP2 = experiment_week(
    2,
    "Dependency digests",
    "Implemented",
    """
## Hypothesis

Git-blob SHA-256 digests of stage inputs allow correct skip/recompute behavior.

## Work

- Stage graph in `stage_definitions.py`
- Ledgers under `artifacts/.pipeline/`
- Unit tests for digest helpers and graph

## Result

Params-only changes invalidate trainer; unchanged upstream stages skip.
""",
)

EXP3 = experiment_week(
    3,
    "CAS packaging gates",
    "Implemented",
    """
## Hypothesis

Immutable CAS publish with metric/schema gates prevents silent regressions.

## Work

- `model_packager` objects/versions/HEAD/pins/RELEASES/catalog
- `binding_mac` integrity
- Contract doc in `cloud-cost/docs/`

## Result

Bootstrap `1.0.0`; dual regressions refuse; inference reads HEAD only.
""",
)

EXP4 = experiment_week(
    4,
    "Model lab election & Compose APIs",
    "Implemented",
    """
## Hypothesis

REXX Borda/Copeland over trial JSON yields a deterministic chosen submission; Compose can serve both APIs.

## Work

- Regina REXX selector, constraints YAML, trials corpus
- Flask `:8081` `/api/select`
- docker-compose + GH Actions smoke

## Result

Election + inference paths covered by integration tests; stack runs locally via Compose.
""",
)

# --- 09 benchmarks ---

BENCH_PRED = fm("Partial") + """# Prediction benchmarks

## Implemented snapshot

| Metric | Value | Dataset |
|--------|-------|---------|
| MAE | ~0.00116 | holdout synthetic |
| RMSE | ~0.00182 | holdout synthetic |
| R² | ~0.999 | holdout synthetic |

## Methodology notes

- Single train/test split from transformation stage
- Not nested CV; not temporal backtest

> **GAP:** No public leaderboard, no baseline linear model comparison checked into `09-benchmarks`. Next: add Ridge/Dummy baselines table.
"""

BENCH_LAT = fm("Gap") + """# Latency benchmarks

> **GAP:** No formal API latency benchmark harness (p50/p95). Next: add k6 or pytest-benchmark for `/api/predict` cold vs warm.
"""

BENCH_PROV = fm("Gap") + """# Provider benchmarks

> **GAP:** No cross-cloud provider cost accuracy study on real invoices. Next: collect anonymized samples per AWS/Azure/GCP.
"""

BENCH_OPT = fm("Gap") + """# Optimization benchmarks

> **GAP:** No prompt/SKU optimization A/B results. Next: define success metric before experiments.
"""

# --- ADRs ---

ADR0001 = fm("Implemented") + """# ADR-0001: Content-addressed (CAS) model packaging

## Status

Accepted — Implemented

## Context

Mutable `model_trainer/model.pkl` paths risk serving untested bytes and make rollback unclear.

## Decision

Publish models into `artifacts/model_bundle/` as a CAS store with `objects/`, `versions/<semver>/manifest.json`, `HEAD`, `pins.json`, `RELEASES`, and `catalog.sqlite`. Promotion gates compare holdout metrics and feature schema; artifacts sealed with digest ring + `binding_mac`.

## Consequences

- Inference must load HEAD only
- Packaging logic is stricter and more complex
- Enables auditability and reproducible rollback by version id
"""

ADR0002 = fm("Implemented") + """# ADR-0002: Dependency-aware re-runs via Git blob digests

## Status

Accepted — Implemented

## Context

Full pipeline recompute on every run wastes time during iteration.

## Decision

Fingerprint stage inputs with **Git blob SHA-256** digests, persist ledgers under `artifacts/.pipeline/`, and skip stages when digests and output validators still match.

## Consequences

- Faster local/CI iteration
- Requires careful dependency declarations in `stage_definitions.py`
- Params changes invalidate trainer without necessarily rebuilding validation
"""

ADR0003 = fm("Implemented") + """# ADR-0003: Flask vs FastAPI for serving

## Status

Accepted — **Flask for now**

## Context

Need a simple synchronous inference API and HTML form; team already had Flask app structure.

## Decision

Keep **Flask** (cloud-cost + model_lab) instead of migrating to FastAPI in this phase.

## Consequences

- Faster delivery; existing templates work
- Manual/OpenAPI-ish spec maintained in docs (not auto-generated)
- Revisit FastAPI when async, validation models, and codegen become priorities

## Alternatives considered

- FastAPI + Pydantic: better schema ergonomics; deferred
- gRPC: overkill for current clients
"""

ADR0004 = fm("Implemented") + """# ADR-0004: REXX Borda/Copeland election for model_lab

## Status

Accepted — Implemented

## Context

Many RandomForest trial JSON files need a transparent, constraint-aware selection — not only “max R²”.

## Decision

Use **Regina REXX** to run **Borda** and **Copeland** social-choice procedures over trials subject to `constraints.yaml`, exposed via CLI and Flask `:8081`.

## Consequences

- System dependency on `regina-rexx` in CI/Docker
- Election logic is auditable and separated from Python training
- Unusual stack choice — documented here so newcomers are not surprised
"""

RISK_REGISTER = fm("Partial") + """# Risk register

| ID | Risk | Likelihood | Impact | Status | Mitigation |
|----|------|------------|--------|--------|------------|
| R1 | Synthetic data → overstated accuracy | High | High | Open | Disclose caveat; plan real billing data |
| R2 | Unauthenticated API abuse | High | Medium | Open | Add token auth + rate limit |
| R3 | CAS volume loss on host | Medium | High | Open | Backup/restore script; DR drill |
| R4 | Regina REXX missing in env | Medium | Medium | Mitigated | Docker/CI install regina-rexx |
| R5 | Metric leakage / tiny test set | High | Medium | Open | Nested CV / larger data later |
| R6 | Scope creep into full LLM platform | Medium | Medium | Open | Gap Register discipline |
| R7 | Dependency digest false skip | Low | High | Monitored | Validators + unit tests |
| R8 | No prod observability → silent fail | High | Medium | Open | Logging/metrics P1 |
| R9 | Supply chain / dep vulns | Medium | Medium | Open | Pin deps; add audit job |
| R10 | Single-node Compose SPOF | High | Medium | Accepted (lab) | Document; K8s later |

> **GAP:** Risks not yet scored with owners in a living tracker outside this markdown. Next: assign Owner column per row.
"""

# weekly reviews
def weekly_review(n: int, highlights: str, next_actions: str) -> str:
    return fm("Partial") + f"""# Weekly review — Week {n:02d}

## Highlights

{highlights.strip()}

## Metrics / demos

- Pipeline/CAS/API status reviewed against CI
- Gaps re-confirmed in portfolio Gap Register

## Next actions

{next_actions.strip()}
"""

WR1 = weekly_review(
    1,
    "- Established dataset + RF baseline\n- Confirmed holdout metrics and synthetic caveat",
    "1. Document feature list\n2. Stabilize params.yaml",
)
WR2 = weekly_review(
    2,
    "- Dependency digest skip path working\n- Stage graph tests green",
    "1. Expand negative tests for false skips\n2. Ensure params-only invalidation",
)
WR3 = weekly_review(
    3,
    "- CAS packaging contract enforced\n- Inference bound to HEAD",
    "1. Backup story for model_bundle\n2. Record refuse-path demos",
)
WR4 = weekly_review(
    4,
    "- model_lab election + Compose dual-API\n- Portfolio docs tree authored",
    "1. Auth spike\n2. Observability spike\n3. Baseline model benchmark table",
)

ROADMAP_13 = fm("Planned") + """# Portfolio roadmap

## Now — harden the lab platform

- Keep CAS + digests + CI green
- Authn spike, structured logs
- Baseline model comparison table

## Next — FinOps data reality

- Ingest sample billing exports
- Prediction vs actual reports
- DQ + drift monitors (log-only)

## Later — LLM intelligence

- Rate cards + tokenization
- Latency & quality models
- Prompt optimization + recommendations

```mermaid
gantt
  title Roadmap (indicative)
  dateFormat  YYYY-MM
  section P0
  VM cost train/serve     :done, 2026-01, 2026-08
  section P1
  Auth + observability    :2026-08, 2026-10
  Billing connector       :2026-09, 2026-11
  section P2
  Latency/quality models  :2026-11, 2027-02
  section P3
  LLM pricing + prompts   :2027-01, 2027-04
```

Dates are portfolio planning aids, not commitments.
"""


def main() -> None:
    # Root index
    write("README.md", DOCS_INDEX)

    # 00
    write("00-vision/README.md", VISION)
    write(
        "00-vision/problem-statement.md",
        fm("Partial")
        + """# Problem statement

Cloud ML projects often leave models as untracked pickles, re-run entire pipelines for tiny edits, and lack promotion gates — making FinOps-facing predictions hard to trust.

This project attacks those failure modes with digest-aware stages, CAS packaging, and explicit APIs, while researching a longer path toward LLM cost intelligence without pretending those modules already exist.
""",
    )

    # 01 research
    write(
        "01-research/README.md",
        section_readme(
            "01 — Research",
            "Partial",
            "Desk research for FinOps / MLOps / LLM cost expansion. Many topics are **Gap**.",
            [
                ("Industry", "industry/overview.md"),
                ("Competitors", "competitors/overview.md"),
                ("LLM pricing", "llm-pricing/overview.md"),
                ("Tokenization", "tokenization/overview.md"),
                ("LLMOps", "llmops/overview.md"),
                ("FinOps", "finops/overview.md"),
                ("Papers", "papers/overview.md"),
                ("References", "references/overview.md"),
            ],
        ),
    )
    write("01-research/industry/overview.md", RESEARCH_INDUSTRY)
    write("01-research/competitors/overview.md", RESEARCH_COMPETITORS)
    write("01-research/llm-pricing/overview.md", RESEARCH_LLM_PRICING)
    write("01-research/tokenization/overview.md", RESEARCH_TOKENIZATION)
    write("01-research/llmops/overview.md", RESEARCH_LLMOPS)
    write("01-research/finops/overview.md", RESEARCH_FINOPS)
    write("01-research/papers/overview.md", RESEARCH_PAPERS)
    write("01-research/references/overview.md", RESEARCH_REFERENCES)

    # 02 product
    write(
        "02-product/README.md",
        section_readme(
            "02 — Product",
            "Partial",
            "PRD, personas, stories, prioritization for the cost intelligence platform.",
            [
                ("PRD", "prd/prd.md"),
                ("Personas", "personas/personas.md"),
                ("User stories", "user-stories/user-stories.md"),
                ("Roadmap", "roadmap/roadmap.md"),
                ("Feature prioritization", "feature-prioritization/prioritization.md"),
            ],
        ),
    )
    write("02-product/prd/prd.md", PRD)
    write("02-product/personas/personas.md", PERSONAS)
    write("02-product/user-stories/user-stories.md", USER_STORIES)
    write("02-product/roadmap/roadmap.md", PRODUCT_ROADMAP)
    write("02-product/feature-prioritization/prioritization.md", FEATURE_PRIO)

    # 03 architecture
    write(
        "03-architecture/README.md",
        section_readme(
            "03 — Architecture",
            "Partial",
            "C4-ish views, sequences, threat/security notes for the implemented Compose system.",
            [
                ("Context", "context/context.md"),
                ("Containers", "containers/containers.md"),
                ("Components", "components/components.md"),
                ("Deployment", "deployment/deployment.md"),
                ("Sequence", "sequence/sequence.md"),
                ("Data flow", "data-flow/data-flow.md"),
                ("ERD", "erd/erd.md"),
                ("Threat model", "threat-model/threat-model.md"),
                ("Caching", "caching/caching.md"),
                ("Scalability", "scalability/scalability.md"),
                ("Security", "security/security.md"),
                ("Decisions", "decisions/README.md"),
            ],
        ),
    )
    write("03-architecture/context/context.md", ARCH_CONTEXT)
    write("03-architecture/containers/containers.md", ARCH_CONTAINERS)
    write("03-architecture/components/components.md", ARCH_COMPONENTS)
    write("03-architecture/deployment/deployment.md", ARCH_DEPLOYMENT)
    write("03-architecture/sequence/sequence.md", ARCH_SEQUENCE)
    write("03-architecture/data-flow/data-flow.md", ARCH_DATAFLOW)
    write("03-architecture/erd/erd.md", ARCH_ERD)
    write("03-architecture/threat-model/threat-model.md", ARCH_THREAT)
    write("03-architecture/caching/caching.md", ARCH_CACHING)
    write("03-architecture/scalability/scalability.md", ARCH_SCALABILITY)
    write("03-architecture/security/security.md", ARCH_SECURITY)
    write("03-architecture/decisions/README.md", ARCH_DECISIONS)

    # 04 ML
    write(
        "04-machine-learning/README.md",
        section_readme(
            "04 — Machine learning",
            "Partial",
            "Only **cost-prediction** is implemented. Other folders document planned gaps.",
            [
                ("Cost prediction", "cost-prediction/overview.md"),
                ("Latency prediction", "latency-prediction/overview.md"),
                ("Quality prediction", "quality-prediction/overview.md"),
                ("Recommendation", "recommendation/overview.md"),
                ("Prompt optimization", "prompt-optimization/overview.md"),
            ],
        ),
    )
    write("04-machine-learning/cost-prediction/overview.md", ML_COST)
    write("04-machine-learning/latency-prediction/overview.md", ML_LATENCY)
    write("04-machine-learning/quality-prediction/overview.md", ML_QUALITY)
    write("04-machine-learning/recommendation/overview.md", ML_RECOMMENDATION)
    write("04-machine-learning/prompt-optimization/overview.md", ML_PROMPT)

    # 05 data
    write(
        "05-data-engineering/README.md",
        section_readme(
            "05 — Data engineering",
            "Partial",
            "CSV-centric lab pipeline with real feature engineering and validation.",
            [
                ("Schemas", "schemas/schemas.md"),
                ("Pipelines", "pipelines/pipelines.md"),
                ("ETL", "etl/etl.md"),
                ("Feature engineering", "feature-engineering/feature-engineering.md"),
                ("Data quality", "data-quality/data-quality.md"),
                ("Data dictionary", "data-dictionary/data-dictionary.md"),
            ],
        ),
    )
    write("05-data-engineering/schemas/schemas.md", DATA_SCHEMAS)
    write("05-data-engineering/pipelines/pipelines.md", DATA_PIPELINES)
    write("05-data-engineering/etl/etl.md", DATA_ETL)
    write("05-data-engineering/feature-engineering/feature-engineering.md", DATA_FE)
    write("05-data-engineering/data-quality/data-quality.md", DATA_QUALITY)
    write("05-data-engineering/data-dictionary/data-dictionary.md", DATA_DICT)

    # 06 API
    write(
        "06-api/README.md",
        section_readme(
            "06 — API",
            "Partial",
            "Documented Flask surfaces; OpenAPI YAML reflects real paths. Webhooks/SDKs are gaps.",
            [
                ("OpenAPI", "openapi/README.md"),
                ("Endpoints", "endpoints/endpoints.md"),
                ("Webhooks", "webhooks/webhooks.md"),
                ("SDKs", "sdks/sdks.md"),
            ],
        ),
    )
    write(
        "06-api/openapi/README.md",
        fm("Implemented")
        + """# OpenAPI

Machine-readable sketch: [`openapi.yaml`](openapi.yaml).

Maintained manually to match Flask routes (not auto-generated from code).
""",
    )
    write("06-api/openapi/openapi.yaml", OPENAPI_YAML)
    write("06-api/endpoints/endpoints.md", API_ENDPOINTS)
    write("06-api/webhooks/webhooks.md", API_WEBHOOKS)
    write("06-api/sdks/sdks.md", API_SDKS)

    # 07 infra
    write(
        "07-infrastructure/README.md",
        section_readme(
            "07 — Infrastructure",
            "Partial",
            "Compose + GHA are real. Observability, alerts, and DR drills are gaps.",
            [
                ("Deployment", "deployment/deployment.md"),
                ("CI/CD", "ci-cd/ci-cd.md"),
                ("Observability", "observability/observability.md"),
                ("Logging", "logging/logging.md"),
                ("Monitoring", "monitoring/monitoring.md"),
                ("Alerts", "alerts/alerts.md"),
                ("Disaster recovery", "disaster-recovery/disaster-recovery.md"),
            ],
        ),
    )
    write("07-infrastructure/deployment/deployment.md", INFRA_DEPLOY)
    write("07-infrastructure/ci-cd/ci-cd.md", INFRA_CICD)
    write("07-infrastructure/observability/observability.md", INFRA_OBS)
    write("07-infrastructure/logging/logging.md", INFRA_LOGGING)
    write("07-infrastructure/monitoring/monitoring.md", INFRA_MON)
    write("07-infrastructure/alerts/alerts.md", INFRA_ALERTS)
    write("07-infrastructure/disaster-recovery/disaster-recovery.md", INFRA_DR)

    # 08 experiments
    write(
        "08-experiments/README.md",
        section_readme(
            "08 — Experiments",
            "Partial",
            "Four weekly experiment logs aligned to what was actually built.",
            [
                ("Week 01", "week-01/experiment.md"),
                ("Week 02", "week-02/experiment.md"),
                ("Week 03", "week-03/experiment.md"),
                ("Week 04", "week-04/experiment.md"),
            ],
        ),
    )
    write("08-experiments/week-01/experiment.md", EXP1)
    write("08-experiments/week-02/experiment.md", EXP2)
    write("08-experiments/week-03/experiment.md", EXP3)
    write("08-experiments/week-04/experiment.md", EXP4)

    # 09 benchmarks
    write(
        "09-benchmarks/README.md",
        section_readme(
            "09 — Benchmarks",
            "Partial",
            "Holdout cost metrics recorded; other benchmark domains are gaps.",
            [
                ("Prediction", "prediction/benchmarks.md"),
                ("Latency", "latency/benchmarks.md"),
                ("Providers", "providers/benchmarks.md"),
                ("Optimization", "optimization/benchmarks.md"),
            ],
        ),
    )
    write("09-benchmarks/prediction/benchmarks.md", BENCH_PRED)
    write("09-benchmarks/latency/benchmarks.md", BENCH_LAT)
    write("09-benchmarks/providers/benchmarks.md", BENCH_PROV)
    write("09-benchmarks/optimization/benchmarks.md", BENCH_OPT)

    # 10 ADRs
    write(
        "10-adrs/README.md",
        fm("Implemented")
        + """# Architecture Decision Records

| ADR | Title | Status |
|-----|-------|--------|
| [0001](ADR-0001-cas-packaging.md) | CAS model packaging | Accepted |
| [0002](ADR-0002-dependency-digests.md) | Git blob dependency digests | Accepted |
| [0003](ADR-0003-flask-vs-fastapi.md) | Flask vs FastAPI | Accepted (Flask) |
| [0004](ADR-0004-rexx-election.md) | REXX Borda/Copeland election | Accepted |
""",
    )
    write("10-adrs/ADR-0001-cas-packaging.md", ADR0001)
    write("10-adrs/ADR-0002-dependency-digests.md", ADR0002)
    write("10-adrs/ADR-0003-flask-vs-fastapi.md", ADR0003)
    write("10-adrs/ADR-0004-rexx-election.md", ADR0004)

    # 11 risks
    write(
        "11-risks/README.md",
        fm("Partial")
        + """# Risks

Primary artifact: [`risk-register.md`](risk-register.md).
""",
    )
    write("11-risks/risk-register.md", RISK_REGISTER)

    # 12 weekly reviews
    write(
        "12-weekly-reviews/README.md",
        section_readme(
            "12 — Weekly reviews",
            "Partial",
            "Retrospectives paired with experiment weeks.",
            [
                ("Week 01", "week-01/review.md"),
                ("Week 02", "week-02/review.md"),
                ("Week 03", "week-03/review.md"),
                ("Week 04", "week-04/review.md"),
            ],
        ),
    )
    write("12-weekly-reviews/week-01/review.md", WR1)
    write("12-weekly-reviews/week-02/review.md", WR2)
    write("12-weekly-reviews/week-03/review.md", WR3)
    write("12-weekly-reviews/week-04/review.md", WR4)

    # 13 roadmap
    write("13-roadmap/README.md", ROADMAP_13)
    write(
        "13-roadmap/milestones.md",
        fm("Planned")
        + """# Milestones

| Milestone | Exit criteria | Status |
|-----------|---------------|--------|
| M0 Lab platform | Train, CAS, predict, elect, CI | **Done** |
| M1 Operability | Auth + metrics + backup drill | Planned |
| M2 Real data | Billing sample vs predict report | Gap |
| M3 LLM FinOps alpha | Rate card calculator + token estimate | Gap |
| M4 Multi-objective | Cost+latency+quality election | Gap |
""",
    )

    # assets
    write(
        "assets/README.md",
        fm("Partial")
        + """# Assets

Diagrams for this portfolio primarily live as **Mermaid blocks inside markdown** (portable, reviewable in PRs).

| Folder | Purpose |
|--------|---------|
| [images/](images/README.md) | Raster/SVG exports (placeholder) |
| [diagrams/](diagrams/README.md) | Exported diagram sources (placeholder) |
| [slides/](slides/README.md) | Slide decks (placeholder) |
""",
    )
    for sub, note in [
        (
            "images",
            "Placeholder for PNG/SVG exports. Prefer Mermaid in section docs until an export is needed.",
        ),
        (
            "diagrams",
            "Placeholder for `.mmd` / draw.io sources. Current architecture diagrams are embedded Mermaid in `03-architecture/` and related docs.",
        ),
        (
            "slides",
            "Placeholder for portfolio slide decks. No slides committed yet.",
        ),
    ]:
        write(
            f"assets/{sub}/README.md",
            fm("Gap")
            + f"# Assets — {sub}\n\n{note}\n\n> **GAP:** No binary assets committed. Next: export key C4/context diagrams if a PDF portfolio is required.\n",
        )
        (DOCS / "assets" / sub / ".gitkeep").write_text("", encoding="utf-8")

    # Patch root README
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    docs_section = """## Documentation

Engineering research portfolio (vision, architecture, ML, ADRs, gaps):

- **[docs/README.md](docs/README.md)** — portfolio index & Gap Register

"""
    if "## Documentation" not in text:
        # Insert after intro paragraph block (after first blank line following title section)
        marker = "## What's included"
        if marker in text:
            text = text.replace(marker, docs_section + marker, 1)
        else:
            text = text.rstrip() + "\n\n" + docs_section
        readme.write_text(text, encoding="utf-8")

    md_count = sum(1 for p in DOCS.rglob("*.md") if p.is_file())
    print(f"DOCS_ROOT={DOCS}")
    print(f"MARKDOWN_FILES={md_count}")
    print("ROOT_README_PATCHED=yes" if "## Documentation" in readme.read_text(encoding="utf-8") else "ROOT_README_PATCHED=no")


if __name__ == "__main__":
    main()
