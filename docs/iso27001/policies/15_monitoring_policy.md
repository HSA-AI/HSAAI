# Monitoring Policy (ISO 27001 A.8.16)

**Document ID:** ISMS-POL-015 | **Version:** 1.0.0 | **Date:** 2026-07-05

## 1. SLOs
- api_gateway: 99.9% availability, p99 < 500ms
- llm_gateway: 99.9% availability, p99 < 5s
- rag_engine: 99.9% availability, p99 < 1s

## 2. Alerting
- 15 Prometheus alert rules (availability, LLM, infrastructure, safety)
- Alert routing: Slack #hsaai-alerts (warning), PagerDuty (critical)
- Alert escalation: 5 min → on-call, 15 min → SRE lead, 30 min → CISO

## 3. Dashboards
- Grafana overview dashboard (8 panels)
- Per-service dashboards
- Executive KPI dashboard

**Owner:** SRE Lead | **Review:** Quarterly
