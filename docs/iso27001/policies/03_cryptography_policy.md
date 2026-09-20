# Cryptography Policy (ISO 27001 A.8.24)

**Document ID:** ISMS-POL-003 | **Version:** 1.0.0 | **Date:** 2026-07-05

## 1. Data in Transit
- TLS 1.3 minimum (TLS 1.2 deprecated)
- mTLS between all microservices
- Certificate management via cert-manager
- HSTS enabled in production

## 2. Data at Rest
- PostgreSQL: TDE (Transparent Data Encryption)
- Redis: encrypted at rest (cloud-managed) or LUKS (self-managed)
- Qdrant: payload encryption
- Backups: AES-256 encryption

## 3. Key Management
- All secrets in HashiCorp Vault (Fail-Closed)
- Key rotation: 90 days for JWT signing keys
- JWT algorithm: RS256 (HS256 prohibited)
- Vault tokens: auto-renewal, 1-hour TTL
- No hardcoded secrets in code or config

## 4. Cryptographic Standards
- Symmetric: AES-256-GCM
- Asymmetric: RSA-2048+ or Ed25519
- Hashing: SHA-256+ (SHA-1 prohibited)
- Password hashing: bcrypt (cost factor ≥ 12)
- Random: cryptographically secure RNG (secrets module)

**Owner:** CISO | **Review:** Annually
