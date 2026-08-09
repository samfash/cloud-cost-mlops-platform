---
Status: Implemented
Owner: Platform
Last updated: 2026-08-09
---

# System context

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
