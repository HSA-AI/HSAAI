# HSAAI Asset Register (ISO 27001 A.5.9)

**Document ID:** ISMS-REG-002 | **Version:** 1.0.0 | **Date:** 2026-07-05

| Asset ID | Asset Name | Type | Owner | Classification | Location | Criticality |
|----------|-----------|------|-------|----------------|----------|-------------|
| AST-001 | api_gateway | Service | Platform Lead | Internal | K8s cluster | Critical |
| AST-002 | auth_service | Service | Platform Lead | Confidential | K8s cluster | Critical |
| AST-003 | llm_gateway | Service | AI Lead | Internal | K8s + GPU | Critical |
| AST-004 | rag_engine | Service | AI Lead | Confidential | K8s cluster | Critical |
| AST-005 | governance | Service | CISO | Confidential | K8s cluster | Critical |
| AST-006 | alignment_service | Service | AI Lead | Internal | K8s cluster | High |
| AST-007 | PostgreSQL | Database | DBA | Confidential | K8s + PV | Critical |
| AST-008 | Qdrant | Vector DB | AI Lead | Confidential | K8s + PV | High |
| AST-009 | Neo4j | Graph DB | AI Lead | Internal | K8s + PV | Medium |
| AST-010 | Redis | Cache | SRE Lead | Internal | K8s | High |
| AST-011 | Keycloak | IdP | CISO | Confidential | K8s | Critical |
| AST-012 | Vault | Secrets | CISO | Restricted | K8s | Critical |
| AST-013 | OPA | Policy Engine | CISO | Internal | K8s | High |
| AST-014 | Kafka | Event Bus | SRE Lead | Internal | K8s | Medium |
| AST-015 | Grafana | Dashboard | SRE Lead | Internal | K8s | Medium |
| AST-016 | AI Constitution | Document | Governance | Confidential | docs/ | High |
| AST-017 | AI Model (Qwen) | AI Model | AI Lead | Restricted | GPU node | Critical |
| AST-018 | Audit Logs | Data | CISO | Confidential | S3 (immutable) | Critical |
| AST-019 | Mobile App | Application | Mobile Lead | Internal | App Store | Medium |
| AST-020 | Web App | Application | Frontend Lead | Internal | CDN | High |

**Total Assets:** 20 | **Critical:** 8 | **High:** 6 | **Medium:** 4 | **Low:** 2
