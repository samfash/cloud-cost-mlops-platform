---
Status: Gap
Owner: Platform
Last updated: 2026-08-09
---

# Webhooks

## Intent

Notify subscribers when CAS HEAD changes or a trial is elected.

## Implemented now

**None.**

> **GAP:** No webhook dispatcher, signatures, or retry policy. Next actions:
> 1. Define events: `model.published`, `model.refused`, `trial.selected`
> 2. HMAC-signed POST with exponential backoff
> 3. Delivery log table
