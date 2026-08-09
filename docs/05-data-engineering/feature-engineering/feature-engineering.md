---
Status: Implemented
Owner: Platform
Last updated: 2026-08-09
---

# Feature engineering

Implemented in `src/utils/feature_engineering.py` and transformation stage.

## Engineered signals (packaged order includes)

- Time parts: `hour`, `day`, `month`, `day_of_week`, `is_weekend`
- Encodings: provider, region, vm_type, target
- Ratios/aggregates: `cpu_memory_ratio`, `total_io`, `io_ratio`, `resource_efficiency`, `latency_throughput_ratio`, `resource_intensity`, `ram_per_vcpu`

Label encoders persisted for serving parity.
