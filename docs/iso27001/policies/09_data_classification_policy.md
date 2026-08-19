# Data Classification Policy (ISO 27001 A.5.12-A.5.14)

**Document ID:** ISMS-POL-009 | **Version:** 1.0.0 | **Date:** 2026-07-05

## 1. Classification Levels
- Public: No restriction (marketing, published policies)
- Internal: HSA employees only (operational data)
- Confidential: Specific department (contracts, financial)
- Restricted: Named individuals only (trade secrets, M&A)
- PII: Contains personal data (Saudi PDPL regulated)
- Financial: Financial data (SOX-equivalent retention)

## 2. Handling Rules
| Level | Encryption | Access | Retention | Disposal |
|-------|-----------|--------|-----------|----------|
| Public | Optional | All | 100 years | N/A |
| Internal | TLS | All employees | 7 years | Secure wipe |
| Confidential | TLS+TDE | Department | 5 years | Secure wipe |
| Restricted | TLS+TDE+Vault | Named | 3 years | Secure wipe+audit |
| PII | TLS+TDE+Vault | Authorized | 3 years (PDPL) | Secure wipe+audit |
| Financial | TLS+TDE | Finance | 7 years | Secure wipe |

## 3. Auto-Classification
- DataGovernanceEngine classifies content automatically
- PII patterns: national ID, IBAN, email, phone, credit card
- Financial keywords: salary, revenue, profit, invoice

**Owner:** Data Governance Officer | **Review:** Annually
