---
Status: Partial
Owner: Platform
Last updated: 2026-08-09
---

# Logging

## Implemented

`src/logging/logger` used by Flask app and pipeline components (file/console style per project setup).

## Gap

> **GAP:** No centralized log aggregation (ELK/Loki). Next: document log fields (`request_id`, `model_version`, `mae` on health).
