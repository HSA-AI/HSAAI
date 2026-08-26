#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-infrastructure/docker/docker-compose.production.yml}"
FIXES_FILE="${FIXES_FILE:-infrastructure/docker/docker-compose.ai-fixes.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"

echo "============================================================"
echo " HSAAI PRODUCTION DEPLOYMENT"
echo "============================================================"

if [[ ! -f "$ENV_FILE" ]]; then
    echo
    echo "ERROR: $ENV_FILE does not exist."
    echo
    echo "Create it using:"
    echo
    echo "  ./scripts/generate-production-env.sh"
    echo
    exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "ERROR: Compose file not found:"
    echo "  $COMPOSE_FILE"
    exit 1
fi

if [[ ! -f "$FIXES_FILE" ]]; then
    echo "ERROR: Compose override not found:"
    echo "  $FIXES_FILE"
    exit 1
fi

echo
echo "[1/7] Validate Compose configuration..."

docker compose \
    --env-file "$ENV_FILE" \
    -f "$COMPOSE_FILE" \
    -f "$FIXES_FILE" \
    config >/tmp/hsai-compose-rendered.yml

echo "[OK] Compose configuration valid."

echo
echo "[2/7] Pull infrastructure images..."

docker compose \
    --env-file "$ENV_FILE" \
    -f "$COMPOSE_FILE" \
    -f "$FIXES_FILE" \
    pull postgres redis qdrant keycloak ollama nginx || true

echo
echo "[3/7] Build services..."

docker compose \
    --env-file "$ENV_FILE" \
    -f "$COMPOSE_FILE" \
    -f "$FIXES_FILE" \
    build

echo
echo "[4/7] Start infrastructure..."

docker compose \
    --env-file "$ENV_FILE" \
    -f "$COMPOSE_FILE" \
    -f "$FIXES_FILE" \
    up -d \
    postgres \
    redis \
    qdrant \
    keycloak \
    ollama

echo
echo "[5/7] Start application services..."

docker compose \
    --env-file "$ENV_FILE" \
    -f "$COMPOSE_FILE" \
    -f "$FIXES_FILE" \
    up -d \
    backend \
    rag_engine \
    llm_gateway \
    multi_agents \
    ai_orchestrator \
    auth_service \
    api_gateway \
    frontend \
    nginx

echo
echo "[6/7] Database initialization..."

docker compose \
    --env-file "$ENV_FILE" \
    -f "$COMPOSE_FILE" \
    -f "$FIXES_FILE" \
    exec -T backend \
    python - <<'PY'
from backend_core.db.database import init_db

init_db()

print("database initialized")
PY

echo
echo "[7/7] Service status..."

docker compose \
    --env-file "$ENV_FILE" \
    -f "$COMPOSE_FILE" \
    -f "$FIXES_FILE" \
    ps

echo
echo "============================================================"
echo " DEPLOYMENT FINISHED"
echo "============================================================"
