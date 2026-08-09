---
Status: Implemented
Owner: Platform
Last updated: 2026-08-09
---

# Data dictionary (core fields)

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
