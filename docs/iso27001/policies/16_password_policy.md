# Password Policy (ISO 27001 A.5.17)

**Document ID:** ISMS-POL-016 | **Version:** 1.0.0 | **Date:** 2026-07-05

## 1. Password Requirements
- Minimum 12 characters
- Must include: uppercase, lowercase, digits, special characters
- Password rotation: 90 days (admin), 180 days (users)
- Password history: last 12 passwords
- Account lockout: 5 failed attempts → 15-minute lockout
- Breached passwords blocked (HaveIBeenPwned API)

## 2. Password Storage
- Passwords hashed with bcrypt (cost factor ≥ 12)
- No plaintext password storage anywhere
- Password reset via secure token (15-min expiry)

## 3. Service Accounts
- Use Vault AppRole or K8s service account JWT
- No shared passwords
- Quarterly rotation

**Owner:** CISO | **Review:** Annually
