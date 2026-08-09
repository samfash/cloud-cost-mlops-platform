---
Status: Implemented
Owner: Platform
Last updated: 2026-08-09
---

# Containers

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
