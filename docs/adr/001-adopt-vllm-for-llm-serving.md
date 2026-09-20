# ADR-001: Adopt vLLM for LLM Serving

**Status:** Accepted
**Date:** 2026-07-04
**Decider:** AI Platform Team

## Context
HSAAI currently uses Ollama for LLM serving. Ollama is good for development
but lacks production-grade features: continuous batching, PagedAttention,
prefix caching, and AWQ quantization. Benchmarks show vLLM is 5-10x faster
than Ollama under concurrent load.

## Decision
Adopt vLLM as the primary LLM serving engine for production.

## Consequences
- **Positive:** 5-10x throughput improvement, lower per-request cost,
  better GPU utilization, supports advanced features (speculative decoding,
  prefix caching).
- **Negative:** Requires GPU (A100/H100 recommended), more complex
  deployment than Ollama.
- **Mitigation:** Keep Ollama as dev fallback; use OpenAI API as
  production fallback when GPU unavailable.

## Alternatives Considered
1. **TGI (Text Generation Inference, HuggingFace):** Similar performance
   to vLLM but less mature ecosystem. Rejected.
2. **SGLang:** Newer, promising, but limited model support. Watch for
   future adoption.
3. **Continue with Ollama:** Insufficient for production load. Rejected.

## References
- vLLM paper: "Efficient Memory Management for Large Language Model
  Serving with PagedAttention" (Kwon et al., 2023)
- vLLM GitHub: https://github.com/vllm-project/vllm
