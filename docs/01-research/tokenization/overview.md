---
Status: Gap
Owner: Platform
Last updated: 2026-08-09
---

# Tokenization & cost attribution

## Concept

Token counts mediate between prompts and dollars. Estimators (tiktoken, SentencePiece approximations) enable pre-flight cost checks.

## Implemented now

**None.** Dataset has no prompt/token fields.

> **GAP:** No tokenizer integration or prompt→token estimator. Next actions:
> 1. Add optional `prompt_text` feature path (planned API)
> 2. Benchmark tiktoken vs vendor billed tokens on a golden set
> 3. Store attribution: `tokens_in, tokens_out, cached_tokens, usd`
