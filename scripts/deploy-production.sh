#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.production.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "ERROR: production compose not found: $COMPOSE_FILE" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: missing production environment file: $ENV_FILE" >&2
  echo "Create it from the production environment example and provide real secrets." >&2
  exit 1
fi

DC=(
  docker compose
  --env-file "$ENV_FILE"
  -f "$COMPOSE_FILE"
)

echo "============================================================"
echo " HSAAI Production Deployment"
echo " Compose: $COMPOSE_FILE"
echo " Env:     $ENV_FILE"
echo "============================================================"

echo
echo "[1/7] Validate production Compose"
"${DC[@]}" config --quiet

mapfile -t SERVICES < <("${DC[@]}" config --services)

has_service() {
  local wanted="$1"
  printf '%s\n' "${SERVICES[@]}" | grep -Fxq "$wanted"
}

REQUIRED_SERVICES=(
  postgres
  redis
  qdrant
  keycloak
  neo4j
  minio
  kafka
  ollama
  backend-core
  auth-service
  rag-service
  llm-gateway
  api-gateway
  web
)

echo
echo "[2/7] Validate production service contract"

missing=0

for service in "${REQUIRED_SERVICES[@]}"; do
  if has_service "$service"; then
    printf 'PASS: %s\n' "$service"
  else
    printf 'FAIL: %s\n' "$service" >&2
    missing=1
  fi
done

if [[ "$missing" -ne 0 ]]; then
  echo "ERROR: production service contract is incomplete." >&2
  exit 1
fi

echo
echo "[3/7] Build and start production stack"

# Docker Compose remains the source of truth for default production services.
# Optional profiled workloads (for example model training) are not forced here.
"${DC[@]}" up -d --build

echo
echo "[4/7] Run database migration"

if has_service "db-migrate"; then
  "${DC[@]}" run --rm db-migrate
else
  "${DC[@]}" exec -T backend-core python - <<'PY'
from backend_core.db.database import init_db

init_db()
print("database initialized")
PY
fi

wait_for_service() {
  local service="$1"
  local attempts="${2:-60}"

  echo "Waiting for $service ..."

  for _ in $(seq 1 "$attempts"); do
    local id
    id="$("${DC[@]}" ps -q "$service" 2>/dev/null || true)"

    if [[ -n "$id" ]]; then
      local state

      state="$(
        docker inspect \
          --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
          "$id" 2>/dev/null || true
      )"

      case "$state" in
        healthy|running)
          echo "PASS: $service ($state)"
          return 0
          ;;
        unhealthy|exited|dead)
          echo "ERROR: $service entered state: $state" >&2
          "${DC[@]}" logs --no-color --tail=100 "$service" || true
          return 1
          ;;
      esac
    fi

    sleep 5
  done

  echo "ERROR: timeout waiting for $service" >&2
  "${DC[@]}" logs --no-color --tail=100 "$service" || true
  return 1
}

echo
echo "[5/7] Validate core runtime"

for service in \
  postgres \
  redis \
  qdrant \
  keycloak \
  backend-core \
  auth-service \
  rag-service \
  llm-gateway \
  api-gateway \
  web
do
  wait_for_service "$service"
done

echo
echo "[6/7] Validate internal application connectivity"

"${DC[@]}" exec -T backend-core python - <<'PY'
import socket
import urllib.request

tcp_targets = [
    ("postgres", 5432),
    ("redis", 6379),
    ("qdrant", 6333),
    ("neo4j", 7687),
    ("kafka", 9092),
    ("minio", 9000),
    ("ollama", 11434),
]

for host, port in tcp_targets:
    with socket.create_connection((host, port), timeout=10):
        print(f"PASS TCP: {host}:{port}")

http_targets = [
    ("auth-service", "http://auth-service:8010/health"),
    ("api-gateway", "http://api-gateway:8000/health"),
    ("llm-gateway", "http://llm-gateway:8090/health"),
]

for name, url in http_targets:
    with urllib.request.urlopen(url, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError(
                f"{name} returned HTTP {response.status}"
            )
        print(f"PASS HTTP: {name} -> {response.status}")
PY

echo
echo "[7/7] Deployment status"

"${DC[@]}" ps

echo
echo "============================================================"
echo " HSAAI PRODUCTION DEPLOYMENT: PASS"
echo "============================================================"
