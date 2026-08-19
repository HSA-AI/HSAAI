# Logging Policy (ISO 27001 A.8.15-A.8.17)

**Document ID:** ISMS-POL-014 | **Version:** 1.0.0 | **Date:** 2026-07-05

## 1. Log Format
- Structured JSON logging (all services)
- Fields: timestamp, severity, service, environment, trace_id, span_id, correlation_id, tenant_id, user_id, message
- Secret redaction: passwords, tokens, API keys, PII automatically redacted

## 2. Log Retention
- Application logs: 30 days (Loki)
- Audit logs: 7 years (immutable, S3 Object Lock)
- Security logs: 90 days (SIEM)

## 3. Log Security
- Logs are append-only (tamper-evident, hash-chained)
- Log access restricted to governance role
- No sensitive data in logs (enforced by StructuredJSONFormatter)

**Owner:** SRE Lead | **Review:** Quarterly
