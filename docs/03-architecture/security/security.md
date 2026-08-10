---
Status: Partial
Owner: Platform
Last updated: 2026-08-10
---

# Security notes

## Implemented

- Packaging integrity (`binding_mac`, digest ring, seal tag)
- Inference loads only CAS HEAD (not trainer dir)
- Non-root container user (`appuser`, uid 10001) after entrypoint seeding
- CI lint (ruff) + tests + informational Trivy scan
- **Optional** `API_KEY` / Bearer auth
- Compose default **rate limit** `RATE_LIMIT_PER_MINUTE=600` (set `0` to disable)
- Probe endpoints + HTML `/` and `/estimate` stay open when `API_KEY` is set

### Enabling optional API protection

```bash
# docker-compose / shell
export API_KEY=replace-me
export RATE_LIMIT_PER_MINUTE=600   # or 0 to disable
docker compose up -d
# clients: -H "X-API-Key: replace-me"  or  -H "Authorization: Bearer replace-me"
```

## Missing controls

- TLS termination in Compose (expect reverse proxy / ingress)
- Fine-grained AuthZ / multi-tenant isolation
- Secrets management (Vault/SOPS)
- Hard SBOM publication gate

> **GAP:** Default Compose still binds open localhost ports. Use `API_KEY` for non-local exposure; terminate TLS at the edge.
