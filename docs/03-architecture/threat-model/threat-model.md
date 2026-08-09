---
Status: Gap
Owner: Platform
Last updated: 2026-08-09
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
| Spoofing | Fake client | **None** (no auth) | High |
| Info disclosure | Feature schema leakage | Minimal | Medium |
| DoS | Flood `/api/predict` | **None** | High |
| Elevation | Write HEAD as non-pipeline user | OS perms only | Medium |

> **GAP:** No formal review, no auth, no rate limit, no signed provenance from CI to prod. Next actions: (1) add API key middleware, (2) document trust boundary diagram, (3) schedule lightweight threat review.
