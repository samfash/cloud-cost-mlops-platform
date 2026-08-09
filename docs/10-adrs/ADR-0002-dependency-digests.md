---
Status: Implemented
Owner: Platform
Last updated: 2026-08-09
---

# ADR-0002: Dependency-aware re-runs via Git blob digests

## Status

Accepted — Implemented

## Context

Full pipeline recompute on every run wastes time during iteration.

## Decision

Fingerprint stage inputs with **Git blob SHA-256** digests, persist ledgers under `artifacts/.pipeline/`, and skip stages when digests and output validators still match.

## Consequences

- Faster local/CI iteration
- Requires careful dependency declarations in `stage_definitions.py`
- Params changes invalidate trainer without necessarily rebuilding validation
