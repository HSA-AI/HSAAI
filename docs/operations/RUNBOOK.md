# HSAAI Operations Runbook (Phase 14)

## Table of Contents
1. [Daily Operations](#daily)
2. [Common Incidents](#incidents)
3. [Deployment Procedures](#deploy)
4. [Backup & Restore](#backup)
5. [Scaling Operations](#scaling)
6. [Security Incidents](#security)

<a name="daily"/>
## 1. Daily Operations

### 1.1 Morning Health Check (5 minutes)
```bash
# Check all services are healthy
kubectl get pods -n hsaai-prod | grep -v Running | grep -v Completed

# Check key dashboards
open https://grafana.hsaai.internal/d/hsaai-overview

# Verify no critical alerts
open https://grafana.hsaai.internal/alerting
```

### 1.2 Verify Backups (10 minutes)
```bash
# Check PostgreSQL backups
kubectl exec -n hsaai-prod patroni-0 -- pg_stat_replication

# Verify Qdrant snapshots
curl http://qdrant:6333/snapshots | jq .

# Test restore (in staging)
./scripts/restore-backup.sh --date yesterday --target staging
```

### 1.3 Review Audit Log
```bash
# Check for security events
curl http://governance:8011/v1/audit/query?action=DENY --limit 50

# Verify audit log integrity
curl http://governance:8011/v1/audit/integrity
```

<a name="incidents"/>
## 2. Common Incidents

### 2.1 LLM Gateway Down
**Symptoms:** Chat returns 503, agents fail to respond
**Impact:** High — all AI features unavailable

**Diagnosis:**
```bash
# Check vLLM pod
kubectl logs -n hsaai-prod -l app=llm-gateway --tail=100

# Check GPU availability
kubectl exec -n hsaai-prod <llm-pod> -- nvidia-smi

# Check fallback to OpenAI
curl http://llm-gateway:8090/health
```

**Resolution:**
1. If GPU OOM: restart pod (`kubectl delete pod -l app=llm-gateway`)
2. If model load failure: check model path in PVC
3. If all vLLM instances down: enable OpenAI fallback in env (`HSAAI_VLLM_ENABLED=false`)
4. If OpenAI key expired: rotate key in Vault

**Escalation:** AI Platform on-call (Slack #ai-incidents)

### 2.2 PostgreSQL High Connections
**Symptoms:** "Too many connections" errors
**Impact:** Medium — writes fail

**Diagnosis:**
```bash
kubectl exec -n hsaai-prod patroni-0 -- psql -c "SELECT count(*) FROM pg_stat_activity;"
```

**Resolution:**
1. Find long-running queries: `SELECT pid, now()-query_start, query FROM pg_stat_activity WHERE query_start < now() - interval '5 minutes';`
2. Kill problematic: `SELECT pg_terminate_backend(pid);`
3. Increase max_connections if recurring
4. Add read replica for analytics queries

### 2.3 Redis Memory Full
**Symptoms:** Cache misses, budget enforcer fails
**Impact:** Medium — performance degradation

**Resolution:**
1. Check memory: `redis-cli INFO memory`
2. Evict large keys: `redis-cli --bigkeys`
3. Restart if corrupted: `kubectl rollout restart -n hsaai-prod deployment/redis`

### 2.4 Audit Log Integrity Failure
**Symptoms:** `verify_integrity` returns false
**Impact:** CRITICAL — possible tampering

**Resolution:**
1. Immediately activate governance review
2. Quarantine affected logs
3. Forensic analysis: identify broken entries
4. If tampering confirmed: trigger security incident response

<a name="deploy"/>
## 3. Deployment Procedures

### 3.1 Standard Deploy (CI/CD)
1. Push to `main` branch
2. CI/CD pipeline runs (10 jobs, ~30 minutes)
3. Auto-deploy to staging
4. DAST scan on staging
5. Manual approval for production
6. Canary deploy (10% traffic, 10 min monitor)
7. Full production rollout

### 3.2 Rollback
```bash
# List recent deployments
helm history hsaai -n hsaai-prod

# Rollback to previous
helm rollback hsaai 1 -n hsaai-prod

# Verify
kubectl get pods -n hsaai-prod -w
```

### 3.3 Emergency Hotfix
```bash
# Build hotfix image
docker build -t ghcr.io/hsaai/<service>:hotfix-$(date +%s) .
docker push ghcr.io/hsaai/<service>:hotfix-$(date +%s)

# Deploy directly (bypass canary — emergency only)
helm upgrade hsaai infrastructure/helm/hsaai \
  -n hsaai-prod \
  --set image.tag=hotfix-<timestamp> \
  --set canary.enabled=false
```

<a name="backup"/>
## 4. Backup & Restore

### 4.1 Backup Schedule
- **PostgreSQL:** Continuous WAL archiving + daily snapshot
- **Qdrant:** Daily snapshot
- **Neo4j:** Daily dump
- **Redis:** RDB every 6 hours (ephemeral — not critical)
- **Audit logs:** Replicated to S3 every 5 minutes

### 4.2 Restore Procedure
```bash
# PostgreSQL point-in-time recovery
./scripts/restore-postgres.sh --timestamp "2026-07-04 14:30:00"

# Qdrant snapshot restore
curl -X POST http://qdrant:6333/collections/hsaai_rag/snapshots/restore \
  -H "Content-Type: application/json" \
  -d '{"snapshot_name": "snapshot-2026-07-04"}'

# Verify restore in staging first!
```

<a name="scaling"/>
## 5. Scaling Operations

### 5.1 Scale LLM Gateway
```bash
# Add more vLLM replicas (each needs a GPU)
kubectl scale -n hsaai-prod deployment/llm-gateway --replicas=3
```

### 5.2 Scale RAG Engine
```bash
# RAG is CPU-bound; add more replicas
kubectl scale -n hsaai-prod deployment/rag-engine --replicas=5
```

### 5.3 Add Qdrant Shard
```bash
# When vector count > 10M per shard
curl -X POST http://qdrant:6333/collections/hsaai_rag/shards \
  -H "Content-Type: application/json" \
  -d '{"shard_count": 4}'
```

<a name="security"/>
## 6. Security Incidents

### 6.1 Prompt Injection Attack
**Detection:** Alert "PromptInjectionBlocked" fires
**Response:**
1. Block source IP in WAF
2. Query audit log for affected tenant
3. Review all agent actions from source
4. If successful injection: trigger kill switch
5. Forensic review + post-mortem

### 6.2 Suspected Data Breach
**Response:**
1. Activate kill switch (`curl -X POST http://safety:8005/v1/safety/kill-switch`)
2. Notify CISO + legal within 1 hour
3. Preserve audit logs (do NOT delete)
4. Notify SDAIA within 72 hours (Saudi PDPL requirement)
5. Forensic analysis
6. Post-mortem within 7 days

### 6.3 Compromised Agent
**Detection:** Agent makes unusual high-severity actions
**Response:**
1. Halt specific agent: `kubectl scale deployment/<agent> --replicas=0`
2. Review all agent actions in last 24h via audit log
3. Revoke agent's service account credentials
4. Review and update agent permissions
