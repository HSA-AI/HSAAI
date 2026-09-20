# SECURITY_VALIDATION_REPORT

**Security approval: FAIL / NOT APPROVED.** No formal exception was supplied. One open High manual finding remains; runtime penetration testing and image scanning are incomplete.

| Scope | Critical | High | Medium | Low | Result |
|---|---|---|---|---|---|
| Bandit actual SAST | Not a Bandit category | 0 | 52 | 57 | Findings retained; no suppressed scan |
| Manual code review | 0 | 1 | 3 | 0 | Open findings below |
| Combined observed findings | 0 | 1 | 55 | 57 | Observed counts only, not a guarantee for untested scope |


Bandit scanned services/packages with `--ignore-nosec` and JSON output, no CLI exclusions or skip list; 40929 LOC, 0 parsing errors. All findings are preserved in `evidence/bandit-final.json`. The scanner has no Critical severity; the zero Critical figure means none identified in the manual/available scans, not proof that none exists anywhere. No finding was removed to obtain a clean report.

Full Ruff: **2417 findings**. Critical undefined-name/syntax selection F821/F822/F823/E9 passed; the full style/quality lint is not clean. Full machine evidence: `ruff-full.json`. Frontend lint passed. npm audit reported no vulnerabilities for the installed frontend lockfile. pip-audit found 0 known vulnerabilities across 117 pinned validation-environment dependencies. This does not cover every Docker base image, GPU/training extra, external service or transitive dependency installed by every image. Complete image SBOM/scanning remains BLOCKED.

Signature secret scan found zero matches across the scanned text scope (`secret-signature-scan.json`). Examples contain placeholders only; production secret files, credentials and private keys are excluded from packaging. Tests use generated or explicitly synthetic test credentials. Signature matching is not a proof of absence of every secret.

Open manual findings:

| ID | Severity | Status | Finding | Evidence | Required action |
|---|---|---|---|---|---|
| MAN-H01 | High | OPEN | Global CoE/FinOps/catalogue data lacks complete tenant/workspace ownership and scoped queries | services/backend_core/enterprise_os/models.py: AICoEProject, AIPolicy, AIRisk, AITraining, CostRecord, Integration; router.py: coe_projects, coe_policies, coe_risks, coe_training, finops_usage | Design and migrate ownership for legacy rows; scope reads/writes and test two tenants. No exception or multi-tenant production approval granted. |
| MAN-M01 | Medium | OPEN | Shared HTTP rate limiter permits requests after a Redis pipeline failure and retains unbounded fallback identities | packages/common/security/rate_limit.py: SlidingWindowRateLimiter.check | Bound fallback storage and enforce an explicit production failure policy; add Redis outage/load acceptance. Separate tenant_limiter.py already defaults fail-closed. |
| MAN-M02 | Medium | OPEN | Some Phase 5 connector errors still return raw exception text | services/backend_core/enterprise_integrations/phase5_connectors.py | Sanitize provider error responses and logs across all additional connectors; the primary real_connectors.py helpers are already sanitized. |
| MAN-M03 | Medium | OPEN | Image tags and model names are not fully pinned to verified immutable digests/revisions | Dockerfiles; Compose; model configuration | Resolve/pin image and model provenance on the build host, generate full image SBOM and scan/sign the actual artifacts. |


Preserved/further repaired security controls: RS256/issuer/audience/expiry validation, trusted client roles, verified tenant/workspace propagation, denied self-approval and independent critical reviewers, knowledge document cleanup failures, parameterized database search, sanitized primary connector/LLM errors, real Fernet encryption, atomic persistent salt creation, rejection of corrupt salt/key mismatch, fail-closed missing permission imports and private config generation. Production DEBUG is explicitly false; Secure cookies/PKCE/CORS examples use company HTTPS origins. Existing no-dev-bypass tests remain enabled.

Review limits for CORS/CSRF/XSS/SQL injection/command injection/SSRF/path traversal/uploads: static and available regression cases were reviewed/run; a systematic live DAST/penetration test against the full authenticated stack is NOT TESTED. In particular connector egress, upload file limits/content validation, proxy/TLS headers, Keycloak refresh/logout/MFA, container privileges/ports, audit delivery and network isolation require live verification. No regulatory certification, ISO/SOC2/GDPR attestation or global security clearance is claimed.
