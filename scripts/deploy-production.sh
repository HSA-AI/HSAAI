#!/usr/bin/env bash
set -euo pipefail
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.production.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Copy .env.production.example first." >&2
  exit 1
fi

echo "[1/6] Pull base images"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull postgres redis qdrant keycloak ollama nginx || true

echo "[2/6] Build HSAAI services"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build

echo "[3/6] Start database services"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d postgres redis qdrant keycloak ollama

echo "[4/6] Start application services"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d backend rag_engine llm_gateway ai_orchestrator auth_service api_gateway frontend nginx

echo "[5/6] Run backend metadata migration/init"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T backend python - <<'PY'
from backend_core.db.database import init_db
init_db()
print('database initialized')
PY

echo "[6/6] Health status"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
for url in http://localhost/health http://localhost:8080/health http://localhost:8000/health; do
  echo "Checking $url"
  curl -fsS "$url" || true
  echo
 done
