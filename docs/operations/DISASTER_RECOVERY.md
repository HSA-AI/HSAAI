# HSAAI Disaster Recovery Guide (Phase 14)

## 1. Recovery Objectives

| System | RPO (Data Loss) | RTO (Downtime) | Strategy |
|--------|----------------|----------------|----------|
| PostgreSQL | < 5 minutes | < 1 hour | WAL archiving + cross-region replica |
| Qdrant | < 24 hours | < 4 hours | Daily snapshots + S3 replication |
| Neo4j | < 24 hours | < 4 hours | Daily dumps + S3 replication |
| Redis | < 6 hours | < 30 minutes | RDB snapshots (non-critical) |
| Audit logs | 0 (real-time) | < 1 hour | Real-time S3 replication |
| LLM models | 0 (immutable) | < 2 hours | Re-download from HuggingFace |
| Configuration | 0 (Git) | < 30 minutes | Git is source of truth |

## 2. Disaster Scenarios

### 2.1 Single Service Failure
**Trigger:** One service (e.g., rag_engine) is down
**Impact:** Partial functionality loss

**Recovery:**
1. Kubernetes auto-restarts failed pods (1-2 min)
2. If persistent: check logs, fix, redeploy
3. If data corruption: restore from backup
4. Estimated RTO: 30 minutes

### 2.2 Availability Zone Failure
**Trigger:** Entire AZ goes down
**Impact:** Reduced capacity

**Recovery:**
1. Patroni fails over to healthy AZ (automatic, ~30s)
2. Qdrant cluster continues with 2 of 3 nodes
3. K8s reschedules pods to healthy AZs
4. Estimated RTO: 15 minutes

### 2.3 Region Failure
**Trigger:** Entire region goes down
**Impact:** Full platform unavailable

**Recovery:**
1. DNS failover to secondary region
2. Promote PostgreSQL cross-region replica to primary
3. Restore Qdrant/Neo4j from S3 snapshots
4. Deploy services via Helm to secondary region K8s cluster
5. Estimated RTO: 4 hours
6. Estimated RPO: 5 minutes (PostgreSQL); 24 hours (Qdrant/Neo4j)

### 2.4 Data Corruption
**Trigger:** Logical corruption (bad migration, accidental delete)
**Impact:** Data integrity compromised

**Recovery:**
1. Stop affected service
2. Identify corruption timestamp from audit log
3. Restore PostgreSQL to point-in-time before corruption
4. Verify in staging first
5. Estimated RTO: 2 hours

### 2.5 Ransomware / Malicious Encryption
**Trigger:** Attacker encrypts production data
**Impact:** CRITICAL

**Recovery:**
1. Isolate affected systems (network segmentation)
2. Do NOT pay ransom
3. Restore from immutable backups (S3 Object Lock)
4. Forensic analysis to identify entry point
5. Patch vulnerability
6. Estimated RTO: 8 hours

## 3. Backup Strategy

### 3.1 PostgreSQL
- **Continuous:** WAL archiving to S3 every 5 minutes
- **Daily:** Full snapshot at 02:00 UTC
- **Retention:** 30 days of WALs, 90 days of snapshots
- **Cross-region:** Replica in secondary region

### 3.2 Qdrant
- **Daily:** Full snapshot at 03:00 UTC
- **Replication:** Snapshots copied to S3 in 2 regions
- **Retention:** 7 daily snapshots

### 3.3 Neo4j
- **Daily:** Full dump at 04:00 UTC
- **Replication:** Dumps copied to S3
- **Retention:** 7 daily dumps

### 3.4 Audit Logs
- **Real-time:** Replicated to S3 every 5 minutes
- **Immutable:** S3 Object Lock (WORM mode)
- **Retention:** 7 years (regulatory requirement)

## 4. DR Drill Procedure (Quarterly)

1. **Plan** (1 week before)
   - Schedule drill window (off-hours)
   - Notify stakeholders
   - Prepare runbook

2. **Execute**
   - Simulate region failure by stopping all services in primary region
   - Initiate failover to secondary region
   - Time the recovery

3. **Verify**
   - All services healthy in secondary region
   - Data integrity verified
   - No data loss beyond RPO

4. **Document**
   - Actual RPO and RTO measured
   - Issues encountered
   - Improvements needed

5. **Improve**
   - Update runbooks based on lessons learned
   - Fix any automation gaps
   - Schedule next drill

## 5. Communication Plan

### Internal
- **Engineering:** Slack #hsaai-incidents
- **Leadership:** Email + SMS for P0 incidents
- **All employees:** Status page (status.hsaai.internal)

### External (if customer-facing impact)
- **Customers:** Email notification within 1 hour
- **Regulators:** SDAIA notification within 72 hours (Saudi PDPL)
- **Public:** Press release for major breaches

## 6. Roles & Responsibilities

| Role | Responsibility |
|------|---------------|
| Incident Commander | Coordinates response, makes go/no-go decisions |
| SRE Lead | Technical recovery execution |
| Security Lead | Forensic analysis, breach notification |
| Comms Lead | Internal + external communication |
| Legal Lead | Regulatory compliance, breach notifications |

## 7. Contact List

| Role | Primary | Secondary |
|------|---------|-----------|
| Incident Commander | oncall-ic@hsaai.internal | (backup) |
| SRE | oncall-sre@hsaai.internal | (backup) |
| Security | security@hsaai.internal | CISO direct |
| Legal | legal@hsaagroup.com | General Counsel |
| SDAIA | (Saudi PDPL breach reporting) | |
