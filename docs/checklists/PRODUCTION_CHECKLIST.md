# Production Acceptance Checklist

- [ ] `npm install` completes in `apps/web`.
- [ ] `npm run build` completes in `apps/web`.
- [ ] `docker compose --env-file .env.production -f docker-compose.production.yml config` is valid.
- [ ] Migrations create `approval_requests`, `llm_usage_logs`, `ai_cost_records`.
- [ ] `/health`, `/ready`, `/metrics` return successfully.
- [ ] PostgreSQL is used; SQLite is not used in production.
- [ ] Qdrant collection exists and persists after restart.
- [ ] Keycloak realm/client/roles are real, not demo-only.
- [ ] Enterprise connectors report configured/not configured without exposing secrets.
- [ ] Human approvals create pending requests for sensitive actions.
- [ ] FinOps logs every chat/LLM request.
- [ ] Prometheus scrapes backend metrics.
- [ ] Grafana loads production dashboard.
