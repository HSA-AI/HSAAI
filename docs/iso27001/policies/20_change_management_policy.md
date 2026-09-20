# Change Management Policy (ISO 27001 A.8.32)

**Document ID:** ISMS-POL-020 | **Version:** 1.0.0 | **Date:** 2026-07-05

## 1. Change Process
- All changes via Pull Request
- PR requires: 1 reviewer, SAST pass, tests pass
- Production deploys: manual approval + canary (10%)
- Rollback: Helm rollback (instant)

## 2. Emergency Changes
- CISO or SRE Lead can approve emergency hotfix
- Post-change review within 48 hours
- All emergency changes logged

## 3. ADR
- Architecture Decision Records for all cross-service changes
- ADRs in docs/adr/

**Owner:** Engineering Lead | **Review:** Quarterly
