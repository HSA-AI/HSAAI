# Patch Management Policy (ISO 27001 A.8.8)

**Document ID:** ISMS-POL-021 | **Version:** 1.0.0 | **Date:** 2026-07-05

## 1. Vulnerability Scanning
- Dependency scan: weekly (pip-audit, npm audit)
- Container scan: on every build (Trivy)
- Infrastructure scan: monthly (kube-bench, Nmap)

## 2. Patching SLA
- Critical (CVSS 9-10): 24 hours
- High (CVSS 7-8.9): 7 days
- Medium (CVSS 4-6.9): 30 days
- Low (CVSS 0-3.9): 90 days

## 3. Patch Testing
- All patches tested in staging first
- Regression tests run before production deploy

**Owner:** SRE Lead | **Review:** Monthly
