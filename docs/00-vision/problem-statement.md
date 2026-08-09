---
Status: Partial
Owner: Platform
Last updated: 2026-08-09
---

# Problem statement

Cloud ML projects often leave models as untracked pickles, re-run entire pipelines for tiny edits, and lack promotion gates — making FinOps-facing predictions hard to trust.

This project attacks those failure modes with digest-aware stages, CAS packaging, and explicit APIs, while researching a longer path toward LLM cost intelligence without pretending those modules already exist.
