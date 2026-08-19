# Media Handling Policy (ISO 27001 A.7.10-A.7.14)

**Document ID:** ISMS-POL-023 | **Version:** 1.0.0 | **Date:** 2026-07-05

## 1. Digital Media
- USB drives: disabled on production servers
- Cloud storage: encrypted (S3 with SSE-KMS)
- File transfer: via secure API only (no FTP)

## 2. Physical Media
- Physical documents: locked in secure cabinets
- Disposal: cross-cut shredding
- Physical media: secure wipe (DoD 5220.22-M) before disposal

## 3. Data Transfer
- Secure file transfer: HTTPS or SFTP
- Large transfers: pre-signed S3 URLs (15-min expiry)
- No email for sensitive data (use HSAAI platform)

**Owner:** IT Manager | **Review:** Annually
