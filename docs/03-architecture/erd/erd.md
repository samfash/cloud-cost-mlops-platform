---
Status: Partial
Owner: Platform
Last updated: 2026-08-09
---

# Logical data model / ERD

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
