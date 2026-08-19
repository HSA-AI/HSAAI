# Secure Coding Standard (ISO 27001 A.8.28)

**Document ID:** ISMS-POL-017 | **Version:** 1.0.0 | **Date:** 2026-07-05

## 1. Python
- Input validation: Pydantic schemas on all endpoints
- SQL: SafeQueryBuilder with allow-list (no f-strings in queries)
- Auth: Fail-Closed (SystemExit on missing auth, never fallback)
- Secrets: Vault only (no os.getenv for sensitive values in production)
- Error handling: Never expose stack traces to users

## 2. TypeScript/Frontend
- Input sanitization on all user inputs
- XSS prevention: React auto-escaping, no dangerouslySetInnerHTML
- CSRF: SameSite cookies + CSRF tokens
- Content Security Policy: default-src 'self'

## 3. Docker
- Multi-stage builds (builder + runtime)
- Non-root user (USER appuser)
- Minimal base image (python:3.12-slim)
- No secrets in images (runtime env vars only)
- Health check on every container

**Owner:** Engineering Lead | **Review:** Quarterly
