---
Status: Implemented
Owner: Platform
Last updated: 2026-08-09
---

# Week 02 — Dependency digests

## Hypothesis

Git-blob SHA-256 digests of stage inputs allow correct skip/recompute behavior.

## Work

- Stage graph in `stage_definitions.py`
- Ledgers under `artifacts/.pipeline/`
- Unit tests for digest helpers and graph

## Result

Params-only changes invalidate trainer; unchanged upstream stages skip.
