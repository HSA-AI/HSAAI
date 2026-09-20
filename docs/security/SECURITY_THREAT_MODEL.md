# HSAAI Security Threat Model

## Core assets

- Internal documents and embeddings.
- User identities and permissions.
- LLM prompts, responses, memories, and audit logs.
- PostgreSQL relational data.
- Qdrant vector data.
- Local model files.
- Encryption keys and Keycloak secrets.

## Main threats

| Threat | Risk | Control |
|---|---|---|
| Data exfiltration through external APIs | Critical | Strict internal-only mode, egress deny, LLM provider allowlist |
| Cross-tenant data leakage | Critical | Tenant/workspace filters on every query, RBAC middleware, tests |
| Prompt injection through documents | High | RAG source separation, system prompt guardrails, audit logging |
| Malicious upload | High | MIME validation, size limits, OCR sandboxing, malware scanning hook |
| Privilege escalation | High | Keycloak roles, backend permission checks, admin audit logs |
| Secret leakage | Critical | Kubernetes secrets, sealed secrets template, no secrets in repo |
| Model endpoint abuse | High | API gateway rate limits, per-user quotas, audit logs |
| Unauthorized internal network access | High | NetworkPolicy, private services, firewall rules |

## Security posture

The recommended production mode is deny-by-default:

1. No external LLM provider.
2. No direct database exposure.
3. No direct Qdrant exposure.
4. No direct Redis exposure.
5. Keycloak and API Gateway are the controlled identity and access entry points.
6. Only frontend/API Gateway are externally reachable, if the deployment is not fully air-gapped.
