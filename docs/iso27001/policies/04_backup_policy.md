# Backup Policy (ISO 27001 A.8.13)

**Document ID:** ISMS-POL-004 | **Version:** 1.0.0 | **Date:** 2026-07-05

## 1. Backup Schedule
- PostgreSQL: WAL archiving (5-min RPO) + daily snapshot
- Qdrant: daily snapshot
- Neo4j: daily dump
- Redis: RDB every 6 hours (ephemeral)
- Audit logs: real-time S3 replication (immutable)

## 2. Retention
- PostgreSQL: 30 days WAL, 90 days snapshots
- Qdrant: 7 daily snapshots
- Audit logs: 7 years (regulatory)

## 3. Restoration
- Monthly restore drill (staging)
- Quarterly DR drill (full failover)
- RTO: < 1 hour (PostgreSQL), < 4 hours (Qdrant)
- RPO: < 5 minutes (PostgreSQL), < 24 hours (Qdrant)

## 4. Verification
- Backup integrity verified after each backup
- Restore test: first Monday of each month
- Backup encryption: AES-256

**Owner:** SRE Lead | **Review:** Quarterly
