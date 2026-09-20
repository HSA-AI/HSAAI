# Business Continuity Policy (ISO 27001 A.5.29-A.5.30)

**Document ID:** ISMS-POL-012 | **Version:** 1.0.0 | **Date:** 2026-07-05

## 1. BCP Objectives
- RTO: < 4 hours for critical AI services
- RPO: < 5 minutes for operational data
- BCP tested annually

## 2. Critical Services Priority
1. Authentication (Keycloak)
2. API Gateway
3. LLM Gateway
4. RAG Engine
5. Governance Service

## 3. Communication Plan
- Internal: Slack #hsaai-incidents
- Leadership: SMS + email for P1
- External: Status page (status.hsaai.internal)

**Owner:** SRE Lead | **Review:** Annually
