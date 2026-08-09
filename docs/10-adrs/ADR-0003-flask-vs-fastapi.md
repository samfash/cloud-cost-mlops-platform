---
Status: Implemented
Owner: Platform
Last updated: 2026-08-09
---

# ADR-0003: Flask vs FastAPI for serving

## Status

Accepted — **Flask for now**

## Context

Need a simple synchronous inference API and HTML form; team already had Flask app structure.

## Decision

Keep **Flask** (cloud-cost + model_lab) instead of migrating to FastAPI in this phase.

## Consequences

- Faster delivery; existing templates work
- Manual/OpenAPI-ish spec maintained in docs (not auto-generated)
- Revisit FastAPI when async, validation models, and codegen become priorities

## Alternatives considered

- FastAPI + Pydantic: better schema ergonomics; deferred
- gRPC: overkill for current clients
