---
Status: Partial
Owner: Platform
Last updated: 2026-08-10
---

# Alerts

## Implemented

Checked-in Prometheus rules at `deploy/prometheus/alerts.yml`, loaded by the Compose `obs` profile:

| Alert | Severity | Intent |
|-------|----------|--------|
| `CloudCostModelNotLoaded` | page | Model gauge down ≥ 2m |
| `CloudCostHigh5xxRate` | page | >5% 5xx for 5m |
| `CloudCostPredictErrorRate` | ticket | >5% predict errors for 5m |
| `CloudCostPredictLatencyP95` | ticket | p95 predict > 1s for 10m |
| `ModelLabSelectErrors` | ticket | >10% select errors for 5m |

CI asserts Prometheus exposes `CloudCostModelNotLoaded` after `docker compose --profile obs up`.

## Still open (GAP)

> **GAP:** No Alertmanager, PagerDuty/Slack notification routes, or on-call schedule.
>
> Next actions:
> 1. Add Alertmanager service to the `obs` profile
> 2. Wire Slack webhook for ticket severity
> 3. Page only on `ModelNotLoaded` and sustained 5xx
