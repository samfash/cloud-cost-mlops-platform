---
Status: Implemented
Owner: Platform
Last updated: 2026-08-09
---

# Pipelines

Stage graph (see `stage_definitions.py`):

1. **data_validation** — CSV + schema → `status.txt`
2. **data_transformation** — features, encoders, train/test
3. **model_trainer** — RF fit → `model.pkl`
4. **model_evaluation** — holdout metrics JSON
5. **model_packaging** — CAS publish

Dependency ledgers: `artifacts/.pipeline/<stage_id>.json`.
