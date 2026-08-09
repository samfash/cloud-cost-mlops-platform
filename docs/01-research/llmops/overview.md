---
Status: Partial
Owner: Platform
Last updated: 2026-08-09
---

# LLMOps / MLOps notes

## Implemented MLOps patterns (this repo)

| Pattern | Where |
|---------|-------|
| Stage graph + validators | `stage_definitions.py` |
| Content digests / skip | `dependency_tracker.py`, `artifacts/.pipeline/` |
| Immutable publish | `model_packager.py`, CAS store |
| CI smoke train+serve | `.github/workflows/ci.yml` |
| Trial election | `model_lab` + Regina REXX |

## Planned LLMOps extensions

- Prompt/version registries
- Eval harnesses for quality + cost jointly
- Shadow traffic for routing policies

> **GAP:** No prompt registry, no LLM eval harness, no online drift monitors. Next: specify an `evals/` layout and metrics contract before coding.
