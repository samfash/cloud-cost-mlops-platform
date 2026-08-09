---
Status: Gap
Owner: Platform
Last updated: 2026-08-09
---

# LLM pricing research

## Why it matters

LLM spend is driven by **tokens in/out**, model tier, caching, batch APIs, and region. A future platform capability would ingest rate cards and predict $ / request.

## Implemented now

**None.** Current model predicts synthetic VM `cost` from infrastructure features, not LLM bills.

> **GAP:** LLM pricing intelligence absent. Next actions:
> 1. Ingest public OpenAI/Anthropic/Google rate cards as versioned YAML
> 2. Define schema: `provider, model, unit, input_price, output_price, cache_price, effective_date`
> 3. Prototype calculator endpoint separate from RF VM cost model
> 4. Document currency and tax assumptions
