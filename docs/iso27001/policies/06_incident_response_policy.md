# Incident Response Policy (ISO 27001 A.5.24-A.5.28)

**Document ID:** ISMS-POL-006 | **Version:** 1.0.0 | **Date:** 2026-07-05

## 1. Incident Classification
- P1 (Critical): Production down, data breach, AI safety violation → Kill Switch
- P2 (Major): Service degradation, security alert, partial outage
- P3 (Minor): Performance issue, non-critical bug
- P4 (Low): Enhancement request, documentation

## 2. Response Times
- P1: Immediate (15 min acknowledgment, 1 hr mitigation)
- P2: 30 min acknowledgment, 4 hr mitigation
- P3: 4 hr acknowledgment, 1 day mitigation
- P4: 1 day acknowledgment, 1 week resolution

## 3. Kill Switch
- Governance role can activate via POST /v1/safety/kill-switch
- Halts ALL agent activity immediately
- Requires manual deactivation

## 4. Breach Notification
- Internal: CISO + Legal within 1 hour
- SDAIA (Saudi PDPL): within 72 hours
- Affected individuals: without undue delay

## 5. Post-Mortem
- All P1/P2 incidents require post-mortem within 7 days
- Root cause analysis (5 Whys)
- Action items tracked to closure

**Owner:** CISO | **Review:** After each P1/P2 incident
