---
Status: Implemented
Owner: Platform
Last updated: 2026-08-09
---

# Week 04 — Model lab election & Compose APIs

## Hypothesis

REXX Borda/Copeland over trial JSON yields a deterministic chosen submission; Compose can serve both APIs.

## Work

- Regina REXX selector, constraints YAML, trials corpus
- Flask `:8081` `/api/select`
- docker-compose + GH Actions smoke

## Result

Election + inference paths covered by integration tests; stack runs locally via Compose.
