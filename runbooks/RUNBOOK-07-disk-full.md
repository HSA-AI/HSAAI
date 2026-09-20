# RUNBOOK-07 — Disk Full Alert

**Trigger**: Prometheus alert
**Severity**: High
**Last Updated**: 2026-08-03 (v0.1.0)

## Impact
- (Describe service impact)

## Diagnosis
```bash
# Step 1: Check service health
curl -f http://localhost:<PORT>/health

# Step 2: Check logs
docker logs hsaai-<service> --tail 100

# Step 3: Check dependencies
docker exec hsaai-<service> ping <dependency>
```

## Immediate Actions
1. (Step 1)
2. (Step 2)
3. (Step 3)

## Root Cause Analysis
- (Common causes)

## Long-term Fixes
- (Preventive measures)

## Escalation
- **L1**: On-call engineer (15 min response)
- **L2**: Service owner (1 hour)
- **L3**: Architecture team (4 hours)
