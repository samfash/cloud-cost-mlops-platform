---
Status: Planned
Owner: Platform
Last updated: 2026-08-09
---

# Portfolio roadmap

## Now — harden the lab platform

- Keep CAS + digests + CI green
- Authn spike, structured logs
- Baseline model comparison table

## Next — FinOps data reality

- Ingest sample billing exports
- Prediction vs actual reports
- DQ + drift monitors (log-only)

## Later — LLM intelligence

- Rate cards + tokenization
- Latency & quality models
- Prompt optimization + recommendations

```mermaid
gantt
  title Roadmap (indicative)
  dateFormat  YYYY-MM
  section P0
  VM cost train/serve     :done, 2026-01, 2026-08
  section P1
  Auth + observability    :2026-08, 2026-10
  Billing connector       :2026-09, 2026-11
  section P2
  Latency/quality models  :2026-11, 2027-02
  section P3
  LLM pricing + prompts   :2027-01, 2027-04
```

Dates are portfolio planning aids, not commitments.
