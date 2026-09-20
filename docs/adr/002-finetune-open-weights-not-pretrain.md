# ADR-002: Fine-Tune Open-Weights Base Instead of Pre-Training

**Status:** Accepted
**Date:** 2026-07-04
**Decider:** AI Platform Team

## Context
HSAAI-R1 was a from-scratch Transformer pre-trained on HSA data.
However, the model was only Xavier-initialized — never actually trained.
Pre-training a competitive LLM requires:
- ~$100M+ in compute (per Chinchilla scaling laws)
- Multiple H100 clusters running for months
- Multi-terabyte high-quality training data

This is uneconomical for any single enterprise, including HSA Group.

## Decision
Stop pre-training efforts. Instead, fine-tune proven open-weights
base models (Llama 3.1 8B, Qwen 2.5 7B, Mistral 7B) on HSA domain
corpora using LoRA + DPO.

## Consequences
- **Positive:** 0.01% of pre-training cost, near-equivalent quality,
  access to community improvements, faster iteration.
- **Negative:** Dependent on base model providers' licensing and
  release schedule. Limited ability to customize architecture.
- **Mitigation:** Use permissively-licensed models (Llama, Qwen);
  maintain fine-tuning adapters that can be re-applied to new base
  versions.

## Alternatives Considered
1. **Continue pre-training HSAAI-R1:** Uneconomical. Rejected.
2. **Use API-only (GPT-4o, Claude):** Vendor lock-in, data residency
   concerns, high per-request cost. Rejected as sole strategy.
3. **Hybrid (local fine-tuned + API fallback):** Chosen. Local model
   for most requests, API for tasks exceeding local capability.

## Implementation
- Base model: Qwen 2.5 7B Instruct (strong Arabic support)
- Fine-tuning: LoRA (r=16, alpha=32) on HSA corpora
- Alignment: DPO on preference data
- Serving: vLLM with AWQ INT4 quantization
- Estimated cost: $5-10K in GPU time for initial fine-tuning

## References
- LoRA paper: "LoRA: Low-Rank Adaptation of Large Language Models"
  (Hu et al., 2021)
- DPO paper: "Direct Preference Optimization" (Rafailov et al., 2023)
- Chinchilla scaling: "Training Compute-Optimal LLMs" (Hoffmann et al., 2022)
