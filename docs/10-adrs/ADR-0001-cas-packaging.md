---
Status: Implemented
Owner: Platform
Last updated: 2026-08-09
---

# ADR-0001: Content-addressed (CAS) model packaging

## Status

Accepted — Implemented

## Context

Mutable `model_trainer/model.pkl` paths risk serving untested bytes and make rollback unclear.

## Decision

Publish models into `artifacts/model_bundle/` as a CAS store with `objects/`, `versions/<semver>/manifest.json`, `HEAD`, `pins.json`, `RELEASES`, and `catalog.sqlite`. Promotion gates compare holdout metrics and feature schema; artifacts sealed with digest ring + `binding_mac`.

## Consequences

- Inference must load HEAD only
- Packaging logic is stricter and more complex
- Enables auditability and reproducible rollback by version id
