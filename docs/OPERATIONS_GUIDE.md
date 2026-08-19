# HSAAI Operations Guide

## 1. Service Management

### Start/Stop Services
```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# Restart a specific service
docker compose restart rag-service

# View logs
docker compose logs -f rag-service
docker compose logs -f llm-gateway
```

### Kubernetes Operations
```bash
# Scale a deployment
kubectl scale deployment rag-engine -n hsaai-prod --replicas=6

# Rolling restart
kubectl rollout restart deployment rag-engine -n hsaai-prod

# View pod logs
kubectl logs -f deployment/rag-engine -n hsaai-prod

# Execute into a pod
kubectl exec -it deployment/rag-engine -n hsaai-prod -- /bin/bash
```

## 2. Database Operations

### Migrations
```bash
# Apply migrations
docker compose exec backend-core alembic upgrade head

# Check current version
docker compose exec backend-core alembic current

# Rollback one migration
docker compose exec backend-core alembic downgrade -1
```

### Backup
```bash
# PostgreSQL backup
docker compose exec postgres pg_dump -U hsaai hsaai_rag > backup_$(date +%Y%m%d).sql

# Qdrant snapshot
curl -X POST http://localhost:6333/collections/hsaai_documents_vectors/snapshots
```

## 3. Monitoring

### Key Metrics to Monitor
| Metric | Alert Threshold | Severity |
|--------|----------------|----------|
| API latency P95 | > 2s | Warning |
| Error rate | > 5% | Critical |
| GPU utilization | > 95% for 30min | Warning |
| Hallucination rate | > 15% | Critical |
| Citation accuracy | < 75% | Warning |
| Database connections | > 80% of pool | Warning |
| Disk usage | > 85% | Warning |

### Grafana Dashboards
- HSAAI Platform Overview
- RAG Engine Performance
- LLM Gateway Metrics
- GPU Utilization
- Security Events
- Cost Analytics (FinOps)

## 4. Incident Response

### Severity Levels
| Level | Response Time | Examples |
|-------|--------------|----------|
| Critical (P0) | 15 min | Platform down, data breach |
| High (P1) | 1 hour | Service degraded, security alert |
| Medium (P2) | 4 hours | Performance issue, bug |
| Low (P3) | 24 hours | Minor issue, enhancement |

### Escalation
1. Alert fires → Alertmanager → PagerDuty (P0/P1) or Slack (P2/P3)
2. On-call engineer investigates
3. Escalate to Platform Lead if unresolved within SLA
4. Post-incident review for P0/P1

## 5. Maintenance Windows

- **Scheduled:** First Saturday of each month, 02:00-06:00 (Asia/Aden)
- **Emergency:** Coordinate with Platform Lead
- **Notification:** 48 hours advance notice via Slack + email

## 6. Capacity Planning

### Current Capacity
| Resource | Current | Target Utilization |
|----------|---------|-------------------|
| CPU | 358 vCPU | < 70% |
| Memory | 1,352 GB | < 80% |
| GPU | 16 A100 80GB | < 85% |
| Storage | 28 TB | < 80% |

### Scaling Triggers
- CPU > 70% for 10 min → HPA scales up
- Memory > 80% for 10 min → HPA scales up
- GPU > 85% → Manual review (add GPU nodes)
- Storage > 80% → Expand vSAN capacity
