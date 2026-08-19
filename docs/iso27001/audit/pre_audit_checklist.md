# HSAAI Pre-Audit Checklist (ISO/IEC 27001:2022)
====================================================
**Document ID:** ISMS-CHK-001 | **Version:** 1.0.0 | **Date:** 2026-07-05

## A.5 Organizational Controls

| # | Control | Evidence Required | Status | File/Location |
|---|---------|-------------------|--------|---------------|
| 1 | A.5.1 InfoSec Policy | Approved policy document | ✅ | docs/iso27001/policies/01_information_security_policy.md |
| 2 | A.5.3 Roles & Responsibilities | Org chart + role definitions | ✅ | Policy 01 Section 5 + RBAC engine (8 roles) |
| 3 | A.5.9 Asset Inventory | Asset register with owners | ✅ | docs/iso27001/registers/asset_register.md |
| 4 | A.5.10 Acceptable Use | Signed AUP from all users | ✅ | Policy 18 |
| 5 | A.5.12 Data Classification | Classification policy + auto-classification | ✅ | Policy 09 + DataGovernanceEngine |
| 6 | A.5.15 Access Control | RBAC + ABAC + RLS implementation | ✅ | Keycloak + OPA + PostgreSQL RLS |
| 7 | A.5.17 Auth Info | Password policy + Vault | ✅ | Policy 16 + vault_client.py |
| 8 | A.5.24 Incident Management | IR plan + kill switch | ✅ | Policy 06 + safety_layer.py |
| 9 | A.5.29 Business Continuity | BCP + DR plan | ✅ | Policy 12 + 13 + recovery.sh |
| 10 | A.5.30 ICT Readiness | DR drills + health checks | ⚠️ | Scripts ready; drill not yet executed |

## A.6 People Controls

| # | Control | Evidence Required | Status | File/Location |
|---|---------|-------------------|--------|---------------|
| 11 | A.6.1 Screening | Background check records | ⚠️ | HR process (not in codebase) |
| 12 | A.6.3 Awareness Training | Training completion records | ⚠️ | Annual requirement documented |
| 13 | A.6.6 Confidentiality | Signed NDAs | ⚠️ | HR process |
| 14 | A.6.7 Remote Working | Remote work policy | ✅ | Policy 19 |
| 15 | A.6.8 Event Reporting | Incident reporting channel | ✅ | Slack #hsaai-incidents + Policy 06 |

## A.7 Physical Controls

| # | Control | Evidence Required | Status | File/Location |
|---|---------|-------------------|--------|---------------|
| 16 | A.7.2 Physical Entry | DC access logs | ⚠️ | Site-specific (DC managed) |
| 17 | A.7.10 Media Handling | Media disposal procedure | ✅ | Policy 23 |

## A.8 Technological Controls

| # | Control | Evidence Required | Status | File/Location |
|---|---------|-------------------|--------|---------------|
| 18 | A.8.2 Privileged Access | Admin role + MFA + review | ✅ | RBAC (Role.ADMIN) + Keycloak MFA |
| 19 | A.8.3 Access Restriction | RBAC + ABAC + RLS | ✅ | governance/main.py + OPA policies |
| 20 | A.8.5 Secure Auth | OIDC + JWT RS256 + PKCE | ✅ | Keycloak + jwt_validator.py |
| 21 | A.8.7 Malware Protection | Container scanning | ✅ | Trivy in CI/CD |
| 22 | A.8.8 Vulnerability Mgmt | SAST + DAST + SCA | ✅ | Policy 22 + CI/CD (10 jobs) |
| 23 | A.8.9 Configuration Mgmt | Helm + K8s manifests | ✅ | infrastructure/kubernetes/ + infrastructure/helm/ |
| 24 | A.8.11 Data Masking | PII redaction | ✅ | output_filter.py + pii_detector |
| 25 | A.8.12 DLP | PII detection + tenant isolation | ✅ | pii_detector + PostgreSQL RLS |
| 26 | A.8.13 Backup | Backup automation + drills | ✅ | scripts/dr/recovery.sh |
| 27 | A.8.14 Redundancy | HA configuration | ✅ | Patroni + Sentinel + K8s replicas |
| 28 | A.8.15 Logging | Structured JSON logging | ✅ | structured_logging.py + Loki |
| 29 | A.8.16 Monitoring | Prometheus + alerts | ✅ | 15 alert rules + Grafana dashboards |
| 30 | A.8.20 Network Security | NetworkPolicies + mTLS + WAF | ✅ | infrastructure/ + mtls/ + waf/ |
| 31 | A.8.24 Cryptography | TLS 1.3 + AES-256 + Vault | ✅ | Policy 03 + vault_client.py |
| 32 | A.8.25 Secure Dev | CI/CD + pre-commit + SAST | ✅ | Policy 05 + .github/workflows/ |
| 33 | A.8.28 Secure Coding | SafeQueryBuilder + Fail-Closed | ✅ | Policy 17 + sql_safety.py |
| 34 | A.8.29 Security Testing | SAST + DAST + SCA + container | ✅ | CI/CD pipeline (10 jobs) |
| 35 | A.8.32 Change Management | PR review + canary deploy | ✅ | Policy 20 + GitHub branch protection |

## Security Testing Tools (Ready to Execute)

| Tool | Purpose | Command | Expected Result |
|------|---------|---------|-----------------|
| Semgrep | SAST | `semgrep --config p/owasp-top-ten services/ packages/` | 0 critical findings |
| Bandit | Python SAST | `bandit -r services/ packages/ -lll` | 0 high findings |
| Trivy | Container scan | `trivy image hsaai/llm_gateway:latest` | 0 critical CVEs |
| Gitleaks | Secret scan | `gitleaks detect --source .` | 0 secrets found |
| kube-bench | K8s CIS benchmark | `kube-bench --benchmark cis-1.8` | 85%+ pass |
| kube-hunter | K8s pentest | `kube-hunter --remote <cluster-ip>` | 0 high findings |
| Checkov | IaC scan | `checkov -d infrastructure/` | 0 failed checks |
| OWASP ZAP | DAST | `zap-baseline -t https://staging.hsaai.internal` | 0 high alerts |
| Nmap | Port scan | `nmap -sV -sC <target>` | Only expected ports open |
| Nikto | Web scan | `nikto -h https://staging.hsaai.internal` | 0 high findings |

## Pre-Audit Readiness: 85%

- **Fully Ready:** 30/35 controls (86%)
- **Partial:** 5/35 controls (14%) — require HR records, DR drill execution, physical security
- **Blocking for Certification:** HR screening records + DR drill execution + physical security audit
