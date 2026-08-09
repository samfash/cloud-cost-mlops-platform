---
Status: Partial
Owner: Platform
Last updated: 2026-08-09
---

# Risk register

| ID | Risk | Likelihood | Impact | Status | Mitigation |
|----|------|------------|--------|--------|------------|
| R1 | Synthetic data → overstated accuracy | High | High | Open | Disclose caveat; plan real billing data |
| R2 | Unauthenticated API abuse | High | Medium | Open | Add token auth + rate limit |
| R3 | CAS volume loss on host | Medium | High | Open | Backup/restore script; DR drill |
| R4 | Regina REXX missing in env | Medium | Medium | Mitigated | Docker/CI install regina-rexx |
| R5 | Metric leakage / tiny test set | High | Medium | Open | Nested CV / larger data later |
| R6 | Scope creep into full LLM platform | Medium | Medium | Open | Gap Register discipline |
| R7 | Dependency digest false skip | Low | High | Monitored | Validators + unit tests |
| R8 | No prod observability → silent fail | High | Medium | Open | Logging/metrics P1 |
| R9 | Supply chain / dep vulns | Medium | Medium | Open | Pin deps; add audit job |
| R10 | Single-node Compose SPOF | High | Medium | Accepted (lab) | Document; K8s later |

> **GAP:** Risks not yet scored with owners in a living tracker outside this markdown. Next: assign Owner column per row.
