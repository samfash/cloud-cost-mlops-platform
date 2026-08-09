---
Status: Partial
Owner: Platform
Last updated: 2026-08-09
---

# User stories

## Implemented

1. As an ML engineer, I can run the full pipeline and get a sealed CAS version so inference never loads a mutable trainer pickle.
2. As an ML engineer, I can re-run training after a params-only change and skip validation/transform when digests match.
3. As an API consumer, I can `POST /api/predict` and receive `{"prediction": float, "status": "success"}`.
4. As a researcher, I can `POST /api/select` on model_lab to elect a trial via Borda/Copeland.

## Planned / Gap

5. As a FinOps analyst, I can compare predicted vs actual cloud invoice lines.  
   > **GAP:** No billing ingestion.
6. As a developer, I can install an official Python SDK.  
   > **GAP:** No SDK package.
7. As an LLM owner, I can estimate token USD before calling a model.  
   > **GAP:** No LLM pricing module.
