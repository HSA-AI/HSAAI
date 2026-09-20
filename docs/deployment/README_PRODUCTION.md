# HSAAI Enterprise AI Platform — Production Runbook

This package upgrades the platform from Pilot/Demo posture to production-ready enterprise deployment without removing existing pages or features.

## Production principles
- PostgreSQL is mandatory in production; SQLite is blocked when `APP_ENV=production`.
- Keycloak/OIDC is the source of truth for identity, roles, and JWT validation.
- Qdrant runs with persistent storage and is required for production RAG.
- Secrets are read only from `.env.production` or external secret references.
- Sensitive actions must create Human-in-the-Loop approval requests.
- LLM requests are logged into FinOps tables.

## First run
```bash
cp .env.production.example .env.production
# edit every CHANGE_ME value and every real enterprise connector value
```

```bash
docker compose --env-file .env.production -f docker-compose.production.yml build
docker compose --env-file .env.production -f docker-compose.production.yml up -d postgres qdrant redis keycloak
docker compose --env-file .env.production -f docker-compose.production.yml run --rm backend python -m backend_core.run_migrations
docker compose --env-file .env.production -f docker-compose.production.yml up -d
```

## Validation
```bash
curl -k https://$DOMAIN_NAME/api/health
curl -k https://$DOMAIN_NAME/api/ready
curl -k https://$DOMAIN_NAME/api/metrics
```

## Production endpoints
- `/health`: process health.
- `/ready`: database + Qdrant + Keycloak issuer readiness.
- `/metrics`: Prometheus metrics.
- `/v1/approvals`: Human approval workflow.
- `/v1/finops/summary`: LLM cost dashboard data.
- `/v1/enterprise-integrations/overview`: connector status without exposing secrets.
