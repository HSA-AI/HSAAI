# RUNBOOK-01: PostgreSQL is Down

## Trigger
- `/health` endpoint returns `{"database": "error"}`
- Prometheus alert `HSAAIPostgresDown` fires
- Grafana dashboard shows no DB connections

## Impact
- **Critical**: All services that depend on PostgreSQL are unavailable:
  - backend_core (all endpoints)
  - auth_service (cannot verify tokens)
  - model_training (cannot schedule jobs)
  - analytics (cannot query metrics)
- Users see 503 errors on all API calls
- New logins fail (Keycloak uses PostgreSQL)

## Diagnosis

```bash
# 1. Check if PostgreSQL container is running
docker ps | grep postgres

# 2. Check PostgreSQL logs
docker logs hsaai-postgres --tail 100

# 3. Try connecting manually
docker exec -it hsaai-postgres psql -U hsaai -d hsaai -c "SELECT 1;"

# 4. Check disk space (most common cause)
docker exec hsaai-postgres df -h /var/lib/postgresql/data

# 5. Check memory
docker stats hsaai-postgres --no-stream
```

## Immediate Actions

### If PostgreSQL process crashed (most common)
```bash
# Restart the container
docker restart hsaai-postgres

# Wait 30 seconds, then verify
sleep 30
docker exec hsaai-postgres psql -U hsaai -d hsaai -c "SELECT 1;"
```

### If disk is full
```bash
# 1. Identify what's consuming space
docker exec hsaai-postgres du -sh /var/lib/postgresql/data/*

# 2. Clear old WAL files if safe
docker exec hsaai-postgres pg_archivecleanup /var/lib/postgresql/data/pg_wal/

# 3. If still full, increase disk size (cloud-specific)
# For AWS EBS: aws ec2 modify-volume --volume-id vol-xxx --size 200
# Then resize filesystem:
docker exec hsaai-postgres resize2fs /dev/xvdf
```

### If OOM killed
```bash
# 1. Check current memory limit
docker inspect hsaai-postgres | grep -i memory

# 2. Increase memory limit in docker-compose.yml:
#    deploy:
#      resources:
#        limits:
#          memory: 4G

# 3. Also tune PostgreSQL:
#    shared_buffers = 1GB
#    effective_cache_size = 3GB
```

## Root Cause Analysis

After stabilization, investigate:
1. Check PostgreSQL logs for the actual error
2. Check `pg_stat_activity` for runaway queries
3. Check `pg_locks` for deadlocks
4. Review recent migrations (alembic upgrade history)

## Long-term Fixes

1. **Set up PostgreSQL HA** (Patroni + 2 replicas) — ADR-011 (planned)
2. **Configure PgBouncer** for connection pooling
3. **Set up automated backups** (every 6 hours, 30-day retention)
4. **Add monitoring alerts** for:
   - Connection pool usage > 80%
   - Disk usage > 85%
   - Replication lag > 60s
5. **Set up read replicas** for analytics queries

## Escalation

- **Level 1**: On-call engineer (this runbook)
- **Level 2**: DBA team (if root cause is data corruption or migration issue)
- **Level 3**: DevOps lead + CTO (if data loss is suspected)

**Contact**: See `runbooks/CONTACTS.md` for current on-call rotation.
