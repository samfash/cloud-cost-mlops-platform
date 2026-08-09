---
Status: Implemented
Owner: Platform
Last updated: 2026-08-09
---

# Schemas

## Source dataset

Path: `cloud-cost/dataset/Cloud_Dataset.csv` (~1000 rows).  
Validated via `schema.yaml` + data_validation stage.

## Feature schema (packaged)

`feature_columns.json` records `feature_order` (25 features) and `n_features`. Schema breaks affect CAS promotion class.

## Example raw fields

`timestamp`, `cpu_usage`, `memory_usage`, `net_io`, `disk_io`, `cloud_provider`, `region`, `vm_type`, `vCPU`, `RAM_GB`, `price_per_hour`, `target`, `latency_ms`, `throughput`, `utilization`, **`cost`** (label).
