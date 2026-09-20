# Deployment

## Requirements
- Linux server with Docker Engine and Docker Compose plugin.
- DNS record pointing `DOMAIN_NAME` to the server.
- Valid Keycloak realm/client configured with roles: `hsaai_admin`, `knowledge_admin`, `document_reviewer`, `document_uploader`, `department_manager`, `ai_user`, `auditor`.
- PostgreSQL, Qdrant, Redis, Keycloak, Prometheus, Grafana are launched by `docker-compose.production.yml`.

## Commands
```bash
cp .env.production.example .env.production
nano .env.production

docker compose --env-file .env.production -f docker-compose.production.yml config
docker compose --env-file .env.production -f docker-compose.production.yml build
docker compose --env-file .env.production -f docker-compose.production.yml up -d
```

## Migrations
```bash
docker compose --env-file .env.production -f docker-compose.production.yml run --rm backend python -m backend_core.run_migrations
```

## SSL
Place certificates under `certbot/conf` as `/etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem` and `privkey.pem`, or run Certbot against `certbot/www`. Nginx redirects HTTP to HTTPS and supports WebSocket upgrade headers.

## Rollback
```bash
docker compose --env-file .env.production -f docker-compose.production.yml down
# restore volumes/backups as required
docker compose --env-file .env.production -f docker-compose.production.yml up -d
```
