#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env.production"

umask 077

echo "============================================================"
echo " HSAAI PRODUCTION SECRET GENERATOR"
echo "============================================================"

if [[ -f "$ENV_FILE" ]]; then
    BACKUP="${ENV_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
    cp "$ENV_FILE" "$BACKUP"
    echo "[BACKUP] Existing .env.production -> $BACKUP"
fi

generate_secret() {
    local bytes="${1:-32}"
    python - "$bytes" <<'PY'
import secrets
import sys

n = int(sys.argv[1])
print(secrets.token_urlsafe(n))
PY
}

generate_hex() {
    local bytes="${1:-32}"
    python - "$bytes" <<'PY'
import secrets
import sys

n = int(sys.argv[1])
print(secrets.token_hex(n))
PY
}

JWT_SECRET="$(generate_secret 64)"
DATA_ENCRYPTION_KEY="$(generate_hex 32)"
POSTGRES_PASSWORD="$(generate_secret 32)"
REDIS_PASSWORD="$(generate_secret 32)"
NEO4J_PASSWORD="$(generate_secret 32)"
ELASTIC_PASSWORD="$(generate_secret 32)"
KEYCLOAK_ADMIN_PASSWORD="$(generate_secret 32)"
MINIO_ROOT_PASSWORD="$(generate_secret 32)"
GRAFANA_ADMIN_PASSWORD="$(generate_secret 32)"

cat > "$ENV_FILE" <<EOF
# ============================================================
# HSAAI PRODUCTION ENVIRONMENT
# GENERATED: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# DO NOT COMMIT THIS FILE
# ============================================================

# ------------------------------------------------------------
# SECURITY
# ------------------------------------------------------------

JWT_SECRET=${JWT_SECRET}
DATA_ENCRYPTION_KEY=${DATA_ENCRYPTION_KEY}

# ------------------------------------------------------------
# POSTGRESQL
# ------------------------------------------------------------

POSTGRES_USER=hsai
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=hsai

# ------------------------------------------------------------
# REDIS
# ------------------------------------------------------------

REDIS_PASSWORD=${REDIS_PASSWORD}
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0

# ------------------------------------------------------------
# NEO4J
# ------------------------------------------------------------

NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=${NEO4J_PASSWORD}

# ------------------------------------------------------------
# ELASTICSEARCH
# ------------------------------------------------------------

ELASTIC_PASSWORD=${ELASTIC_PASSWORD}

# ------------------------------------------------------------
# KEYCLOAK
# ------------------------------------------------------------

KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=${KEYCLOAK_ADMIN_PASSWORD}

# ------------------------------------------------------------
# MINIO
# ------------------------------------------------------------

MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}

# ------------------------------------------------------------
# GRAFANA
# ------------------------------------------------------------

GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}

# ------------------------------------------------------------
# INTERNAL SERVICE URLs
# ------------------------------------------------------------

BACKEND_URL=http://backend:8000
API_GATEWAY_URL=http://api_gateway:8080
RAG_ENGINE_URL=http://rag_engine:8030
LLM_GATEWAY_URL=http://llm_gateway:8090
AI_ORCHESTRATOR_URL=http://ai_orchestrator:8020
MULTI_AGENTS_URL=http://multi_agents:8040
ANALYTICS_URL=http://analytics:8070

# ------------------------------------------------------------
# APPLICATION
# ------------------------------------------------------------

ENVIRONMENT=production
LOG_LEVEL=INFO

# ------------------------------------------------------------
# SECURITY FLAGS
# ------------------------------------------------------------

INTERNAL_ONLY_MODE=true
ALLOW_EXTERNAL_APIS=false
STRICT_EGRESS_DENY=true
EOF

chmod 600 "$ENV_FILE"

echo
echo "[OK] Production secrets generated."
echo "[OK] File: $ENV_FILE"
echo "[OK] Permissions:"
ls -l "$ENV_FILE"

echo
echo "IMPORTANT:"
echo "1. Do NOT commit .env.production"
echo "2. Do NOT paste its contents into chat"
echo "3. Keep a secure offline backup of the secrets"
echo
echo "Next:"
echo "  docker compose --env-file .env.production \\"
echo "    -f infrastructure/docker/docker-compose.production.yml config --quiet"
