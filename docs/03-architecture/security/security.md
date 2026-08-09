---
Status: Partial
Owner: Platform
Last updated: 2026-08-09
---

# Security notes

## Implemented

- Packaging integrity (`binding_mac`, digest ring, seal tag)
- Inference loads only CAS HEAD (not trainer dir)
- CI lint (ruff) + tests

## Missing controls

- TLS termination config in Compose
- Authentication / authorization
- Secrets management
- Dependency scanning gate (beyond what GH may provide by default)
- SBOM publication

> **GAP:** APIs are open on localhost ports by default. Next: document network exposure; add optional `API_TOKEN` check.
