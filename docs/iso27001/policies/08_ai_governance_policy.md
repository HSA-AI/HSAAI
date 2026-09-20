# AI Governance Policy (ISO 27001 + NIST AI RMF)

**Document ID:** ISMS-POL-008 | **Version:** 1.0.0 | **Date:** 2026-07-05

## 1. AI Constitution
- 16 articles governing AI behavior (docs/constitution.md)
- Prohibited actions: non-compliant contracts, competitor pricing, financial transactions, production data modification
- Required behaviors: cite sources, disclose limitations, escalate when unsure

## 2. Alignment Layer
- Constitutional AI (self-critique + external review)
- All AI responses pass through alignment before delivery
- External reviewer (GPT-4o) blocks unsafe responses

## 3. Safety Layer
- Tool severity classification (1-4)
- Severity 1 (Catastrophic): two-person approval
- Severity 2 (Serious): one-person approval
- Kill switch: governance role can halt all agents

## 4. Model Security
- Model chain: Qwen (local) → Llama (fallback) → GPT-4o (cloud)
- No data leaves HSA infrastructure unless explicitly approved
- LoRA fine-tuning on HSA domain corpora only
- Model outputs filtered for PII, toxicity, hallucination

## 5. Evaluation
- RAG metrics: precision, recall, MRR, nDCG, faithfulness, hallucination rate
- Continuous monitoring of AI quality
- Monthly model evaluation against held-out test set

**Owner:** AI Governance Committee | **Review:** Quarterly
