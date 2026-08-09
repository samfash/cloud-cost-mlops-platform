---
Status: Partial
Owner: Platform
Last updated: 2026-08-09
---

# Vision

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
