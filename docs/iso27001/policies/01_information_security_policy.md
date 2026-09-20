# HSAAI Information Security Policy (ISO/IEC 27001:2022 — A.5.1)

**Document ID:** ISMS-POL-001
**Version:** 1.0.0
**Effective Date:** 2026-07-05
**Owner:** Chief Information Security Officer (CISO)
**Approved By:** HSA Group Board of Directors

---

## 1. Purpose

This Information Security Policy establishes the framework for protecting information assets within the HSAAI Enterprise AI Platform operated by Hayel Saeed Anam Group (HSA Group). It ensures alignment with ISO/IEC 27001:2022, NIST CSF 2.0, and Saudi PDPL.

## 2. Scope

This policy applies to:
- All HSAAI platform services, APIs, databases, and infrastructure
- All employees, contractors, and third parties accessing HSAAI
- All data processed, stored, or transmitted through the platform
- All environments: development, staging, and production

## 3. Information Security Principles

1. **Confidentiality** — Information is accessible only to authorized persons
2. **Integrity** — Information accuracy and completeness are maintained
3. **Availability** — Information is accessible when needed
4. **Least Privilege** — Access is granted on a need-to-know basis
5. **Defense in Depth** — Multiple layers of security controls
6. **Zero Trust** — Never trust, always verify (no implicit trust)
7. **Fail-Closed** — Systems fail to a secure state, never to an open state
8. **Accountability** — All actions are logged and attributable

## 4. Information Security Objectives

| Objective | Target | Metric |
|-----------|--------|--------|
| Availability | 99.9% | Monthly uptime |
| Security Incidents | 0 critical/year | Incident count |
| Vulnerability Remediation | < 30 days (High), < 7 days (Critical) | MTTR |
| Access Review | 100% quarterly | Review completion |
| Training Completion | 100% annually | Training records |
| Backup Success | 99.9% | Backup logs |
| Pen Test Findings | 0 Critical/High at closure | Pentest report |

## 5. Roles and Responsibilities

### 5.1 Board of Directors
- Approve information security policy
- Ensure adequate resources for ISMS
- Review security posture quarterly

### 5.2 CISO
- Own the Information Security Management System (ISMS)
- Maintain policies, procedures, and controls
- Report security posture to the Board
- Lead incident response

### 5.3 Platform Engineering Team
- Implement security controls in code
- Follow secure coding standards
- Participate in security testing
- Remediate vulnerabilities within SLA

### 5.4 All Users
- Comply with security policies
- Report security incidents immediately
- Complete mandatory security training
- Protect credentials and access tokens

## 6. Policy Statements

### 6.1 Access Control
All access to HSAAI is authenticated via Keycloak OIDC with JWT. RBAC and ABAC are enforced via OPA. Multi-tenant isolation is enforced via PostgreSQL Row-Level Security. No anonymous access is permitted in production.

### 6.2 Cryptography
All data in transit uses TLS 1.3. All data at rest is encrypted via PostgreSQL TDE. JWT tokens use RS256 (not HS256). Secrets are managed via HashiCorp Vault (Fail-Closed mode — no dev tokens in production).

### 6.3 Secure Development
All code is reviewed before merge. SAST (Semgrep), dependency scanning (pip-audit), container scanning (Trivy), and secret scanning (Gitleaks) are mandatory in CI/CD. Pre-commit hooks enforce code quality.

### 6.4 Incident Response
Security incidents are classified P1-P4. P1 incidents activate the kill switch (halting all AI agents). All incidents are logged in the audit trail and reviewed within 72 hours per Saudi PDPL.

### 6.5 Business Continuity
RPO: PostgreSQL < 5 minutes, Qdrant < 24 hours. RTO: < 1 hour for critical services. DR drills are conducted quarterly.

### 6.6 AI Security
All AI responses pass through Constitutional AI alignment (self-critique + external review). Prompt injection is blocked by the prompt firewall. PII is redacted before LLM calls. Agent actions are classified by severity (1-4) with approval routing.

### 6.7 Supplier Security
Third-party integrations (SAP, AD, SuccessFactors) use OAuth2 with token caching. All connectors have circuit breakers. Vendor access is time-boxed and audited.

## 7. Compliance

This policy supports compliance with:
- ISO/IEC 27001:2022 (Information Security Management)
- NIST Cybersecurity Framework 2.0
- Saudi PDPL (Personal Data Protection Law)
- GDPR (for European operations)
- OWASP ASVS 4.0
- OWASP LLM Top 10

## 8. Review

This policy is reviewed annually or after significant security incidents.

---

**Classification:** Confidential — HSA Internal Use Only
**Next Review:** 2027-07-05
