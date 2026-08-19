# HSAAI Change Management

## 1. Release Process

### Versioning
- Format: `MAJOR.MINOR.PATCH` (Semantic Versioning)
- MAJOR: Breaking changes (API, database schema)
- MINOR: New features (backward compatible)
- PATCH: Bug fixes and security patches

### Release Stages
1. **Development** — Feature branch + code review
2. **Staging** — Deploy to staging cluster, integration testing
3. **Production** — Canary deployment (1 replica) → full rollout

## 2. Database Migration Policy

- All schema changes via Alembic migrations
- Migrations tested in staging before production
- Zero-downtime migrations preferred (additive changes)
- Destructive migrations require maintenance window

### Migration Commands
```bash
# Generate migration
alembic revision --autogenerate -m "description"

# Apply
alembic upgrade head

# Rollback
alembic downgrade -1
```

## 3. Deployment Process

### Pre-Deployment Checklist
- [ ] All tests pass (unit, integration, security)
- [ ] Code reviewed and approved
- [ ] Database migrations tested in staging
- [ ] Security scan (Trivy, Bandit) passed
- [ ] Image signed (cosign)
- [ ] SBOM generated
- [ ] Runbook updated
- [ ] Rollback plan documented

### Deployment Steps
```bash
# 1. Build and sign image
docker build -t registry.hsaai.internal/hsaai/rag-engine:vX.Y.Z .
cosign sign --key env://COSIGN_PRIVATE_KEY registry.hsaai.internal/hsaai/rag-engine:vX.Y.Z

# 2. Deploy to staging
kubectl apply -k deploy/overlays/staging
kubectl rollout status deployment/rag-engine -n hsaai-staging

# 3. Verify staging
python3 hsaai-vmware-readiness.py

# 4. Deploy to production (canary)
kubectl set image deployment/rag-engine rag-engine=...:vX.Y.Z -n hsaai-prod
kubectl rollout status deployment/rag-engine -n hsaai-prod
```

### Rollback
```bash
kubectl rollout undo deployment/rag-engine -n hsaai-prod
alembic downgrade -1
```

## 4. Changelog Format

```markdown
## [X.Y.Z] — YYYY-MM-DD

### Added
- New feature description

### Changed
- Modified behavior description

### Fixed
- Bug fix description

### Security
- Security patch description
```

## 5. Approval Matrix

| Change Type | Approver | Downtime |
|-------------|----------|----------|
| Patch (bug fix) | DevOps Lead | No |
| Minor (new feature) | Platform Lead | No |
| Major (breaking) | IT Director | Yes (maintenance window) |
| Security (critical) | Security Officer | Emergency |
| Database schema | DBA + Platform Lead | Coordinated |

## 6. Communication

| Audience | Channel | Timing |
|----------|---------|--------|
| DevOps team | Slack #hsaai-deploys | Real-time |
| Department managers | Email | 48h before production |
| All users | In-app banner | 24h before maintenance |
| Executive team | Email | Monthly summary |
