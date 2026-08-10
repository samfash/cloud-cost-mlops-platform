---
Status: Partial
Owner: Platform
Last updated: 2026-08-10
---

# Latency benchmarks

## Implemented

- Integration smoke `tests/integration/test_predict_latency.py` asserts warm `/api/predict` wall time &lt; 250ms (local RF / cache path).
- Prometheus histogram `predict_latency_seconds` + Grafana overview panel.

## Still open

> Formal k6 multi-VU soak and published p50/p95 tables across hardware classes remain open.
