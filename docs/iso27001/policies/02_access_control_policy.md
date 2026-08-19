# Access Control Policy (ISO 27001 A.5.15-A.5.18)

**Document ID:** ISMS-POL-002 | **Version:** 1.0.0 | **Date:** 2026-07-05

## 1. Purpose
Define access control requirements for HSAAI platform.

## 2. Authentication
- All access requires Keycloak OIDC authentication (JWT)
- MFA required for admin and governance roles
- Service-to-service uses mTLS + service accounts
- No anonymous access in production (Fail-Closed)

## 3. Authorization
- RBAC: 8 roles (super_admin, admin, governance, builder, analyst, employee, external_auditor, service_account)
- ABAC: 6 policies (tenant isolation, clearance, department, business hours, prod protection, auditor timebox)
- OPA policies enforce access at API and tool levels
- PostgreSQL Row-Level Security for tenant isolation

## 4. Access Review
- Quarterly access review for all users
- Automated de-provisioning on termination
- Privileged access reviewed monthly
- Service accounts rotated quarterly

## 5. Password Policy
- Minimum 12 characters
- Must include uppercase, lowercase, digits, special characters
- Password rotation: 90 days (admin), 180 days (users)
- Password history: last 12 passwords
- Account lockout: 5 failed attempts → 15-minute lockout
- Breached passwords blocked via HaveIBeenPwned API

## 6. Session Management
- JWT lifetime: 15 minutes (access token)
- Refresh token: 7 days with rotation
- Idle timeout: 30 minutes
- Concurrent sessions: max 3 per user

**Owner:** CISO | **Review:** Quarterly
