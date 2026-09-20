# Secure Development Policy (ISO 27001 A.8.25-A.8.28)

**Document ID:** ISMS-POL-005 | **Version:** 1.0.0 | **Date:** 2026-07-05

## 1. Secure Coding
- OWASP ASVS 4.0 Level 2 compliance
- Input validation on all API endpoints (Pydantic schemas)
- Parameterized queries only (SafeQueryBuilder with allow-list)
- Output encoding for all responses
- No dynamic SQL, no string concatenation in queries

## 2. Code Review
- All PRs require 1 reviewer approval
- SAST scan (Semgrep) must pass
- Secret scan (Gitleaks) must pass
- Dependency scan (pip-audit) must pass
- No new TODO/FIXME allowed

## 3. CI/CD Pipeline (10 jobs)
1. Code Quality (ruff, mypy, eslint)
2. SAST (Semgrep, Bandit, CodeQL)
3. Dependency Scan (pip-audit, npm audit, Syft SBOM)
4. Container Scan (Trivy, Grype)
5. IaC Validation (kubeval, Checkov)
6. Unit Tests (pytest, 95% coverage target)
7. Build & Push (Docker, GHCR)
8. Deploy Staging (Helm)
9. DAST (OWASP ZAP)
10. Canary Prod (10% → monitor → promote)

## 4. Pre-commit Hooks
- ruff (lint + format)
- mypy (type check)
- bandit (SAST)
- detect-secrets + trufflehog
- hadolint (Dockerfile)
- shellcheck
- markdownlint

**Owner:** Engineering Lead | **Review:** Quarterly
