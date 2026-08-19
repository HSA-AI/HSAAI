# HSAAI Security Model

## 1. Zero Trust Architecture

HSAAI implements NIST SP 800-207 Zero Trust principles:
- Every request authenticated and authorized
- No implicit trust based on network location
- Least privilege access enforcement
- Continuous monitoring and audit

## 2. Authentication

- **Protocol:** Keycloak OIDC + PKCE
- **MFA:** TOTP required for all roles
- **Session:** 8-hour timeout, JWT with JWKS
- **Account Lockout:** 5 failed attempts → 15-minute lockout
- **Password Policy:** 15+ characters, complexity required, 90-day rotation

## 3. Authorization

### RBAC Roles (7)
| Role | Level | Permissions |
|------|-------|------------|
| Platform Administrator | L1 | Full access (15 permissions) |
| AI Governance Officer | L2 | AI safety, approvals, evaluations |
| Data Owner | L3 | Knowledge bases, data access |
| Department Manager | L4 | Department users and agents |
| AI Developer | L5 | Prompts, agents, RAG pipelines |
| Employee User | L6 | Consume approved agents |
| Auditor | L3 | Read-only audit and analytics |

### ABAC Enforcement
- Central Policy Decision Point (PDP)
- Fail-closed in production
- Attribute-based: user, resource, environment, action

### Classification Levels
| Level | Access |
|-------|--------|
| PUBLIC | All users |
| INTERNAL | INTERNAL, CONFIDENTIAL, RESTRICTED clearance |
| CONFIDENTIAL | CONFIDENTIAL, RESTRICTED clearance |
| RESTRICTED | RESTRICTED clearance only |

## 4. Tenant Isolation

- PostgreSQL RLS: `USING (tenant_id = current_setting('app.tenant_id'))`
- Qdrant: Mandatory `tenant_id` filter in every query
- Application: `TenantGuard` enforces JWT-derived tenant_id
- No cross-tenant data access possible

## 5. Secrets Management

- HashiCorp Vault (3-node HA cluster)
- External Secrets Operator for Kubernetes
- No plaintext secrets in code or environment files
- Secret rotation: 90-day policy for API keys

## 6. Data Protection

- AES-256 encryption at rest (PostgreSQL, MinIO, vSAN)
- TLS 1.3 in transit (mTLS via Istio)
- PII detection: 9 patterns (Yemeni ID, Saudi Iqama, credit cards, IBAN, email, phone, IP)
- Prompt injection defense: 9 attack patterns blocked
- HMAC-signed audit trail (tamper-proof)

## 7. Compliance

| Standard | Status |
|----------|--------|
| ISO 27001:2022 | 95% (38/40 controls) |
| OWASP ASVS Level 2 | 91% (191/210 controls) |
| CIS Docker Benchmark v1.6.0 | Compliant |
| NIST AI RMF | 100% (16/16 controls) |
| NIST SP 800-207 (Zero Trust) | 86% (6/7 tenets) |
