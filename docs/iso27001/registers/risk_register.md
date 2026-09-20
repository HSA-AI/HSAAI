# HSAAI Risk Register (ISO 27001 A.6.1.2)

**Document ID:** ISMS-REG-001 | **Version:** 1.0.0 | **Date:** 2026-07-05

| Risk ID | Asset | Threat | Vulnerability | Impact (1-5) | Likelihood (1-5) | Risk Score | Risk Level | Risk Owner | Treatment | Residual Risk |
|---------|-------|--------|---------------|--------------|------------------|------------|------------|------------|-----------|---------------|
| RISK-001 | LLM Gateway | Prompt Injection | No input sanitization (was) | 5 | 3 | 15 | High | AI Platform Lead | Mitigate: prompt_firewall.py | Low (3) |
| RISK-002 | All Services | Auth Bypass | Fallback auth granting unknown identity (was) | 5 | 2 | 10 | High | CISO | Mitigate: Fail-Closed auth | Low (2) |
| RISK-003 | PostgreSQL | Data Breach | Cross-tenant access (was IDOR) | 5 | 2 | 10 | High | CISO | Mitigate: Claims-based tenant isolation + RLS | Low (2) |
| RISK-004 | All Services | CORS Bypass | Wildcard origins (was) | 4 | 3 | 12 | High | CISO | Mitigate: centralized CORS config | Low (2) |
| RISK-005 | Vault | Secret Exposure | Dev-only-token fallback (was) | 5 | 2 | 10 | High | CISO | Mitigate: Fail-Closed Vault | Low (2) |
| RISK-006 | Docker Images | Privilege Escalation | Running as root (was, 4 services) | 4 | 3 | 12 | High | DevOps Lead | Mitigate: non-root user in all Dockerfiles | Low (2) |
| RISK-007 | Dependencies | Known CVEs | Unpinned versions (was) | 3 | 4 | 12 | High | DevOps Lead | Mitigate: unified versions + CI scanning | Low (3) |
| RISK-008 | AI Agents | Excessive Agency | No approval for high-risk actions (was) | 5 | 2 | 10 | High | AI Governance | Mitigate: safety_layer.py + severity classification | Low (2) |
| RISK-009 | Audit Logs | Tampering | No integrity verification (was) | 4 | 2 | 8 | Medium | CISO | Mitigate: hash-chained audit log | Low (2) |
| RISK-010 | RAG Engine | Hallucination | No grounding verification (was) | 3 | 4 | 12 | High | AI Platform Lead | Mitigate: RAG metrics + faithfulness scoring | Low (3) |
| RISK-011 | K8s Cluster | Pod Escape | No Pod Security Standards (partial) | 4 | 2 | 8 | Medium | DevOps Lead | Mitigate: Pod Security Admission + NetworkPolicies | Low (2) |
| RISK-012 | Backup | Data Loss | No restore verification (was) | 4 | 3 | 12 | High | SRE Lead | Mitigate: recovery.sh drill (quarterly) | Low (3) |
| RISK-013 | SIEM Integration | Log Loss | Default HMAC secret (was) | 3 | 3 | 9 | Medium | CISO | Mitigate: no default secrets + Vault | Low (2) |
| RISK-014 | Model Training | GPU Unavailability | No GPU for fine-tuning | 3 | 3 | 9 | Medium | AI Platform Lead | Accept: use GPT-4o fallback | Medium (9) |
| RISK-015 | Multi-Region | Region Failure | Single region deployment | 5 | 2 | 10 | High | SRE Lead | Mitigate: multi_region.py config | Low (3) |

**Total Risks:** 15 | **Critical:** 0 | **High:** 9 | **Medium:** 5 | **Low:** 1 (after treatment)

**Next Review:** 2026-10-05 (Quarterly)
