#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.production.yml}"
ENV_FILE="${ENV_FILE:-.env}"

DC=(
  docker compose
  --env-file "$ENV_FILE"
  -f "$COMPOSE_FILE"
)

cleanup() {
  rc=$?

  if [[ "$rc" -ne 0 ]]; then
    echo
    echo "===== E2E FAILURE STATUS ====="
    "${DC[@]}" ps --all || true

    echo
    echo "===== APPLICATION LOGS ====="
    "${DC[@]}" logs \
      --no-color \
      --tail=120 \
      backend-core auth-service llm-gateway api-gateway \
      keycloak kafka ollama \
      2>/dev/null || true
  fi

  "${DC[@]}" down --remove-orphans >/dev/null 2>&1 || true
  exit "$rc"
}

trap cleanup EXIT

echo "===== VALIDATE COMPOSE ====="
"${DC[@]}" config --quiet

required=(
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
  llm-gateway
  api-gateway
)

mapfile -t actual < <("${DC[@]}" config --services)

for service in "${required[@]}"; do
  if printf '%s\n' "${actual[@]}" | grep -Fxq "$service"; then
    echo "PASS service: $service"
  else
    echo "ERROR: missing service $service" >&2
    exit 1
  fi
done

echo
echo "===== BUILD APPLICATION SERVICES ====="

"${DC[@]}" build \
  backend-core \
  auth-service \
  llm-gateway \
  api-gateway \
  minio \
  minio-init

echo
echo "===== START DATA SERVICES ====="

"${DC[@]}" up -d --no-deps \
  postgres \
  redis \
  qdrant

echo
echo "===== POSTGRES READY ====="

for attempt in $(seq 1 36); do
  if "${DC[@]}" exec -T postgres \
      pg_isready -U hsaai -d hsaai >/dev/null 2>&1; then
    echo "PASS PostgreSQL"
    break
  fi

  if [[ "$attempt" -eq 36 ]]; then
    echo "ERROR: PostgreSQL timeout" >&2
    exit 1
  fi

  sleep 5
done

"${DC[@]}" exec -T postgres \
  psql -U hsaai -d hsaai \
  -v ON_ERROR_STOP=1 \
  -Atqc 'SELECT 1' \
  | grep -qx 1

echo
echo "===== REDIS READY ====="

for attempt in $(seq 1 24); do
  if "${DC[@]}" exec -T redis redis-cli ping 2>/dev/null \
      | grep -qx PONG; then
    echo "PASS Redis"
    break
  fi

  if [[ "$attempt" -eq 24 ]]; then
    echo "ERROR: Redis timeout" >&2
    exit 1
  fi

  sleep 5
done

echo
echo "===== QDRANT READY ====="

# Production does not require Qdrant to publish its port on the host.
# Probe it from the Compose network instead.
"${DC[@]}" run --rm --no-deps   --entrypoint python3   backend-core - <<'PYQDRANT'
import sys
import time
import urllib.request

url = "http://qdrant:6333/healthz"

for attempt in range(1, 25):
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            if response.status == 200:
                print("PASS Qdrant internal health")
                sys.exit(0)
    except Exception as exc:
        print(
            f"Qdrant attempt {attempt}/24: "
            f"{type(exc).__name__}: {exc}"
        )

    time.sleep(5)

raise SystemExit("ERROR: Qdrant internal health timeout")
PYQDRANT

echo
echo "===== START ENTERPRISE DEPENDENCIES ====="

"${DC[@]}" up -d --no-deps \
  neo4j \
  minio \
  kafka \
  ollama

sleep 10

echo
echo "===== KAFKA FUNCTIONAL CHECK ====="

for attempt in $(seq 1 30); do
  if "${DC[@]}" exec -T kafka \
      kafka-topics \
      --bootstrap-server kafka:9092 \
      --list >/dev/null 2>&1; then
    echo "PASS Kafka broker"
    break
  fi

  if [[ "$attempt" -eq 30 ]]; then
    echo "ERROR: Kafka timeout" >&2
    exit 1
  fi

  sleep 4
done

"${DC[@]}" exec -T kafka \
  kafka-topics \
  --bootstrap-server kafka:9092 \
  --create \
  --if-not-exists \
  --topic hsaai-enterprise-e2e \
  --partitions 1 \
  --replication-factor 1

"${DC[@]}" exec -T kafka \
  kafka-topics \
  --bootstrap-server kafka:9092 \
  --list \
  | grep -qx hsaai-enterprise-e2e

echo "PASS Kafka topic lifecycle"

echo
echo "===== START KEYCLOAK ====="

"${DC[@]}" up -d --no-deps keycloak

# Probe Keycloak through the same internal network used by HSAAI services.
"${DC[@]}" run --rm --no-deps \
  --entrypoint python3 \
  backend-core - <<'PYKEYCLOAK'
import json
import sys
import time
import urllib.request

discovery = (
    "http://keycloak:8080/realms/hsaai/"
    ".well-known/openid-configuration"
)

for attempt in range(1, 61):
    try:
        with urllib.request.urlopen(
            discovery,
            timeout=5,
        ) as response:
            if response.status == 200:
                print("PASS Keycloak realm")
                break
    except Exception as exc:
        print(
            f"Keycloak attempt {attempt}/60: "
            f"{type(exc).__name__}: {exc}"
        )

    time.sleep(5)
else:
    raise SystemExit("ERROR: Keycloak internal health timeout")

jwks_url = (
    "http://keycloak:8080/realms/hsaai/"
    "protocol/openid-connect/certs"
)

with urllib.request.urlopen(
    jwks_url,
    timeout=10,
) as response:
    if response.status != 200:
        raise SystemExit(
            f"ERROR: Keycloak JWKS HTTP {response.status}"
        )

    data = json.load(response)

keys = data.get("keys")

assert isinstance(keys, list)
assert keys, "JWKS contains no keys"

print("PASS Keycloak JWKS")
PYKEYCLOAK

echo
echo "===== RUN DATABASE MIGRATIONS ====="

if "${DC[@]}" config --services | grep -qx 'db-migrate'; then
  "${DC[@]}" run --rm db-migrate
  echo "PASS Database migrations"
else
  echo "ERROR: db-migrate service not found"
  exit 1
fi

echo
echo "===== START BACKEND ====="

"${DC[@]}" up -d --no-deps backend-core

for attempt in $(seq 1 48); do
  if "${DC[@]}" exec -T backend-core python3 -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5)" \
    >/dev/null 2>&1; then

    echo "PASS backend-core"
    break
  fi

  if [[ "$attempt" -eq 48 ]]; then
    echo "ERROR: backend-core timeout" >&2
    exit 1
  fi

  sleep 5
done

echo
echo "===== ENTERPRISE DEPENDENCY CONNECTIVITY ====="

"${DC[@]}" exec -T backend-core python3 - <<'PY'
import socket
import urllib.request

tcp_targets = [
    ("postgres", 5432),
    ("redis", 6379),
    ("qdrant", 6333),
    ("neo4j", 7687),
    ("minio", 9000),
    ("kafka", 9092),
    ("ollama", 11434),
    ("keycloak", 8080),
]

for host, port in tcp_targets:
    with socket.create_connection((host, port), timeout=10):
        print(f"PASS TCP {host}:{port}")

http_targets = [
    ("Qdrant", "http://qdrant:6333/healthz"),
    ("MinIO", "http://minio:9000/minio/health/live"),
    ("Ollama", "http://ollama:11434/api/tags"),
    (
        "Keycloak",
        "http://keycloak:8080/realms/hsaai/.well-known/openid-configuration",
    ),
]

for name, url in http_targets:
    with urllib.request.urlopen(url, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError(f"{name}: HTTP {response.status}")
        print(f"PASS HTTP {name}: {response.status}")
PY

echo
echo "===== START APPLICATION PATH ====="

"${DC[@]}" up -d --no-deps \
  auth-service \
  llm-gateway \
  api-gateway

check_http_inside() {
  local service="$1"
  local url="$2"

  for attempt in $(seq 1 48); do
    if "${DC[@]}" exec -T "$service" python3 -c \
      "import urllib.request; urllib.request.urlopen('$url', timeout=5)" \
      >/dev/null 2>&1; then

      echo "PASS $service -> $url"
      return 0
    fi

    sleep 5
  done

  echo "ERROR: $service health timeout: $url" >&2
  return 1
}

check_http_inside \
  auth-service \
  http://127.0.0.1:8010/health

check_http_inside \
  llm-gateway \
  http://127.0.0.1:8090/health

check_http_inside \
  api-gateway \
  http://127.0.0.1:8000/health

echo
echo "===== SERVICE-TO-SERVICE E2E ====="

"${DC[@]}" exec -T backend-core python3 - <<'PY'
import urllib.request

targets = [
    ("Auth", "http://auth-service:8010/health"),
    ("LLM", "http://llm-gateway:8090/health"),
    ("Gateway", "http://api-gateway:8000/health"),
]

for name, url in targets:
    with urllib.request.urlopen(url, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError(
                f"{name} returned HTTP {response.status}"
            )

        print(f"PASS backend-core -> {name}: {response.status}")
PY

echo
echo "===== FINAL STATUS ====="

"${DC[@]}" ps --all

echo
echo "HSAAI ENTERPRISE E2E CORE PATH: PASS"
