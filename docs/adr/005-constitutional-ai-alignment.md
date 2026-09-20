# ADR-005: Implement Constitutional AI for Alignment

**Status:** Accepted
**Date:** 2026-07-04

## Context
HSAAI agents can perform high-stakes actions (approve contracts, modify
production data). Without alignment, misaligned agents can cause
significant harm. The current platform has no alignment layer.

## Decision
Implement Constitutional AI (Bai et al., 2022) with:
1. Written HSA AI Constitution (docs/constitution.md)
2. Self-Critique Engine (agents critique their own responses)
3. External Reviewer (separate LLM evaluates responses)

## Consequences
- **Positive:** Principled behavior, auditable decisions, reduced harm.
- **Negative:** 2-3x latency per request (multiple LLM calls).
- **Mitigation:** Apply external review only to sensitive queries.

## Reference
- Constitutional AI: https://arxiv.org/abs/2212.08073
