# Disaster Recovery Plan (ISO 27001 A.5.30)

**Document ID:** ISMS-POL-013 | **Version:** 1.0.0 | **Date:** 2026-07-05

## 1. DR Scenarios
- Single service failure: K8s auto-restart (1-2 min)
- AZ failure: Patroni failover (30 sec)
- Region failure: DNS failover + replica promotion (4 hr RTO)
- Data corruption: Point-in-time recovery (2 hr RTO)

## 2. DR Procedures
- scripts/dr/recovery.sh backup — full backup
- scripts/dr/recovery.sh restore-pg — PostgreSQL restore
- scripts/dr/recovery.sh failover — region failover
- scripts/dr/recovery.sh drill — quarterly drill

## 3. DR Roles
- Incident Commander: coordinates response
- SRE Lead: technical recovery
- Security Lead: forensic analysis
- Comms Lead: notifications

**Owner:** SRE Lead | **Review:** Quarterly
