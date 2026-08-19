# HSAAI Penetration Test Checklist (v4.0)

Pre-production penetration test checklist. Must be executed by a qualified
third-party security firm before Enterprise Production deployment.

## Scope

- **Target:** HSAAI Platform (all 14 microservices + infrastructure)
- **Environment:** Staging (identical to production)
- **Duration:** 2-3 weeks
- **Methodology:** OWASP Testing Guide v4.2 + NIST SP 800-115

---

## 1. Authentication Testing

- [ ] **OTG-AUTHN-001:** Test for credentials transported over encrypted channel
- [ ] **OTG-AUTHN-002:** Test for default credentials
- [ ] **OTG-AUTHN-003:** Test for weak lock out policy (brute force)
- [ ] **OTG-AUTHN-004:** Test for bypassing authentication schema
- [ ] **OTG-AUTHN-005:** Test for vulnerable remember password
- [ ] **OTG-AUTHN-006:** Test for browser cache weakness
- [ ] **OTG-AUTHN-007:** Test for weak password policy
- [ ] **OTG-AUTHN-008:** Test for weak security question/answer
- [ ] **OTG-AUTHN-009:** Test for weak password change/reset
- [ ] **OTG-AUTHN-010:** Test for weaker authentication in alternative channel

### HSAAI-Specific Auth Tests:
- [ ] Verify PKCE flow: code_verifier NOT in /v1/auth/authorize response
- [ ] Verify PKCE state validation: invalid state → 400
- [ ] Verify PKCE state is single-use (replay → 400)
- [ ] Verify MFA endpoints require authentication
- [ ] Verify MFA secret NOT in /v1/mfa/enroll response
- [ ] Verify refresh token rotation (old token invalid after refresh)
- [ ] Verify httpOnly + Secure + SameSite=Strict on all cookies
- [ ] Verify no tokens in localStorage/sessionStorage

---

## 2. Authorization Testing

- [ ] **OTG-AUTHZ-001:** Test path traversal (bypass authorization schema)
- [ ] **OTG-AUTHZ-002:** Test for bypassing authorization schema
- [ ] **OTG-AUTHZ-003:** Test for privilege escalation
- [ ] **OTG-AUTHZ-004:** Test for insecure indirect object references (IDOR)

### HSAAI-Specific Authz Tests:
- [ ] Verify tenant isolation: user from tenant A cannot access tenant B's data
- [ ] Verify X-Tenant-ID header is NOT trusted (JWT only)
- [ ] Verify role enforcement: ai_user cannot access admin endpoints
- [ ] Verify ABAC policies: business hours restriction enforced
- [ ] Verify ABAC policies: confidential data requires clearance
- [ ] Verify workflow /approve uses JWT claims (not query param)

---

## 3. Session Management

- [ ] **OTG-SESS-001:** Test for session management schema
- [ ] **OTG-SESS-002:** Test for cookies attributes
- [ ] **OTG-SESS-003:** Test for session fixation
- [ ] **OTG-SESS-004:** Test for exposed session variables
- [ ] **OTG-SESS-005:** Test for CSRF
- [ ] **OTG-SESS-006:** Test for logout functionality
- [ ] **OTG-SESS-007:** Test session timeout
- [ ] **OTG-SESS-008:** Test for session puzzling

---

## 4. Input Validation Testing

- [ ] **OTG-INP-001:** Test for reflected XSS
- [ ] **OTG-INP-002:** Test for stored XSS
- [ ] **OTG-INP-003:** Test for HTTP verb tampering
- [ ] **OTG-INP-004:** Test for HTTP parameter pollution
- [ ] **OTG-INP-005:** Test for SQL injection
- [ ] **OTG-INP-006:** Test for LDAP injection
- [ ] **OTG-INP-007:** Test for ORM injection
- [ ] **OTG-INP-008:** Test for XML injection
- [ ] **OTG-INP-009:** Test for code injection
- [ ] **OTG-INP-010:** Test for command injection
- [ ] **OTG-INP-011:** Test for buffer overflow
- [ ] **OTG-INP-012:** Test for incubated vulnerability
- [ ] **OTG-INP-013:** Test for HTTP splitting/smuggling

### HSAAI-Specific Input Tests:
- [ ] Verify path traversal protection in dataset upload (name=../../etc)
- [ ] Verify path traversal protection in RAG upload (tenant_id=../../)
- [ ] Verify filename sanitization (secure_filename)
- [ ] Verify file size limit (50MB)
- [ ] Verify file extension allowlist

---

## 5. Prompt Injection Testing (AI-Specific)

- [ ] Test "Ignore previous instructions" attack
- [ ] Test "[INST] system override [/INST]" injection
- [ ] Test "<|im_start|> system" injection
- [ ] Test "<<SYS>>" injection
- [ ] Test DAN (Do Anything Now) jailbreak
- [ ] Test "reveal your system prompt" attack
- [ ] Test RAG poisoning (upload doc with embedded instructions)
- [ ] Test cross-tenant injection (doc in tenant A affects tenant B queries)
- [ ] Verify prompt injection defense blocks high-risk queries
- [ ] Verify RAG context is sanitized before LLM call

---

## 6. API Testing

- [ ] **OTG-API-001:** Test API for mass assignment
- [ ] **OTG-API-002:** Test API for rate limiting
- [ ] **OTG-API-003:** Test API for excessive data exposure
- [ ] **OTG-API-004:** Test API for improper asset management
- [ ] **OTG-API-005:** Test API for BOLA (Broken Object Level Authorization)
- [ ] **OTG-API-006:** Test API for broken function level authorization
- [ ] **OTG-API-007:** Test API for security misconfiguration
- [ ] **OTG-API-008:** Test API for injection
- [ ] **OTG-API-009:** Test API for improper assets management

### HSAAI-Specific API Tests:
- [ ] Verify all 8 microservices require authentication (no unauthenticated access)
- [ ] Verify WebSocket /ws requires JWT
- [ ] Verify /docs, /openapi.json are NOT public (admin only)
- [ ] Verify per-tenant rate limiting
- [ ] Verify CORS allowlist (no wildcard)

---

## 7. Infrastructure Testing

- [ ] Test Docker container isolation (no host access)
- [ ] Test K8s NetworkPolicies (no cross-namespace access)
- [ ] Test PodSecurityStandards (no root, no privileged)
- [ ] Verify all images are signed (cosign verify)
- [ ] Verify all images have SBOM attached
- [ ] Test mTLS between services
- [ ] Verify Vault secrets (no env var leaks)
- [ ] Test PostgreSQL HA failover
- [ ] Test Redis Sentinel failover
- [ ] Test Qdrant cluster resilience

---

## 8. Data Protection Testing

- [ ] Verify PII detection blocks documents with national IDs
- [ ] Verify PII detection blocks documents with credit card numbers
- [ ] Verify audit logs are HMAC-signed (tamper detection)
- [ ] Verify audit logs are streamed to SIEM
- [ ] Verify data at rest is encrypted (Fernet)
- [ ] Verify data in transit is encrypted (TLS/mTLS)
- [ ] Verify soft-delete works (data recoverable)
- [ ] Verify hard-delete works (data unrecoverable)

---

## 9. Dependency Testing

- [ ] Run `pip-audit` on all Python services
- [ ] Run `npm audit` on frontend
- [ ] Run `trivy` on all Docker images
- [ ] Verify no CRITICAL CVEs in production images
- [ ] Verify SBOM exists for all images

---

## 10. Social Engineering (Optional)

- [ ] Phishing simulation (if in scope)
- [ ] Pretexting test (if in scope)
- [ ] Physical security test (if in scope)

---

## Sign-off

- [ ] All Critical findings remediated
- [ ] All High findings remediated or risk-accepted
- [ ] Penetration test report signed by CISO
- [ ] Production deployment approved by security team

**Pen Test Firm:** ___________________________
**Date:** ___________________________________
**Sign-off:** _______________________________
