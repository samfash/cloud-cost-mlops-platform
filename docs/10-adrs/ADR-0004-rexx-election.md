---
Status: Implemented
Owner: Platform
Last updated: 2026-08-09
---

# ADR-0004: REXX Borda/Copeland election for model_lab

## Status

Accepted — Implemented

## Context

Many RandomForest trial JSON files need a transparent, constraint-aware selection — not only “max R²”.

## Decision

Use **Regina REXX** to run **Borda** and **Copeland** social-choice procedures over trials subject to `constraints.yaml`, exposed via CLI and Flask `:8081`.

## Consequences

- System dependency on `regina-rexx` in CI/Docker
- Election logic is auditable and separated from Python training
- Unusual stack choice — documented here so newcomers are not surprised
