---
Status: Partial
Owner: Platform
Last updated: 2026-08-09
---

# Industry landscape — FinOps & cloud cost ML

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
