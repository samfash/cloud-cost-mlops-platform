---
Status: Partial
Owner: Platform
Last updated: 2026-08-10
---

# Threat model (draft)

## Assets

- Sealed model blobs and HEAD pointer
- Inference API availability
- Training dataset integrity

## STRIDE sketch

| Threat | Example | Mitigations today | Residual |
|--------|---------|-------------------|----------|
| Tampering | Swap `model.pkl` | CAS digests, binding_mac | Local FS still writable by host |
| Spoofing | Fake client | Optional `API_KEY` / Bearer | Off by default on localhost |
| Info disclosure | Feature schema leakage | Minimal surface | Medium |
| DoS | Flood `/api/predict` | Default Compose rate limit (600/min), tunable | Per-process only |
| Elevation | Write HEAD as non-pipeline user | Non-root `appuser` after seed | Host volume mount still trusted |

## Trust boundary (Compose)

```text
[Browser / API client]
        |
        v
[Flask Gunicorn :8080 / :8081]  -- optional API_KEY, rate limit, predict cache
        |
        v
[CAS model_bundle volume]  -- sealed HEAD only for inference
```

> Remaining: formal review sign-off, TLS at edge, shared rate-limit store across replicas.
