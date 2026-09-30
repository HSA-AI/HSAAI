#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

MODE="${1:-contract}"

wait_http() {
  local url="$1"
  local label="$2"
  local attempts="${3:-30}"

  for attempt in $(seq 1 "${attempts}"); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      echo "PASS: ${label}"
      return 0
    fi

    echo "Waiting for ${label} (${attempt}/${attempts})"
    sleep 5
  done

  echo "ERROR: ${label} did not become ready"
  return 1
}

contract_check() {
  local compose_file="docker-compose.production.yml"

  echo "===== PRODUCTION RUNTIME VERSION CONTRACT ====="

  expected=(
    "image: confluentinc/cp-kafka:7.7.1"
    "image: quay.io/keycloak/keycloak:25.0.6"
    "image: grafana/loki:3.3.2"
    "image: ghcr.io/mlflow/mlflow:v2.18.0"
    "image: neo4j:5"
    "image: ollama/ollama:0.4.7"
    "image: postgres:16"
    "image: qdrant/qdrant:v1.12.1"
    "image: redis:7-alpine"
    "image: grafana/tempo:2.6.0"
    "image: thanosio/thanos:v0.37.0"
  )

  for item in "${expected[@]}"; do
    if ! grep -Fq "${item}" "${compose_file}"; then
      echo "ERROR: production runtime contract missing: ${item}"
      exit 1
    fi

    echo "PASS: ${item}"
  done

  grep -Fq \
    "MINIO_REF: RELEASE.2025-10-15T17-29-55Z" \
    "${compose_file}"

  grep -Fq \
    "MC_REF: RELEASE.2025-08-13T08-35-41Z" \
    "${compose_file}"

  grep -Fq \
    "ARG MINIO_REF=RELEASE.2025-10-15T17-29-55Z" \
    infrastructure/minio/Dockerfile.server

  grep -Fq \
    "ARG MC_REF=RELEASE.2025-08-13T08-35-41Z" \
    infrastructure/minio/Dockerfile.mc

  echo "PASS: MinIO production source ref"
  echo "PASS: MinIO MC production source ref"

  env_file="infrastructure/docker/.env.production"
  created_env=0

  if [[ ! -e "${env_file}" ]]; then
    : > "${env_file}"
    created_env=1
  fi

  cleanup_contract() {
    if [[ "${created_env}" == "1" ]]; then
      rm -f "${env_file}"
    fi
  }

  trap cleanup_contract EXIT

  export DOMAIN_NAME="${DOMAIN_NAME:-ci.hsaai.invalid}"
  export KEYCLOAK_ISSUER="${KEYCLOAK_ISSUER:-http://keycloak:8080/realms/hsaai}"
  export KEYCLOAK_CLIENT_ID="${KEYCLOAK_CLIENT_ID:-hsaai-frontend}"
  export KEYCLOAK_REALM="${KEYCLOAK_REALM:-hsaai}"

  while IFS= read -r var; do
    [[ -z "${var}" ]] && continue

    if [[ -z "${!var+x}" ]]; then
      export "${var}=hsaai-ci-placeholder"
    fi
  done < <(
    grep -hoE '\$\{[A-Z][A-Z0-9_]*:\?[^}]*\}' \
      "${compose_file}" 2>/dev/null \
      | sed -E 's/^\$\{([A-Z][A-Z0-9_]*):\?.*$/\1/' \
      | sort -u
  )

  docker compose \
    -f "${compose_file}" \
    config >/tmp/hsaai-production-runtime-parity.yml

  echo "PASS: production compose renders successfully"

  echo
  echo "===== RESOLVED PRODUCTION IMAGES ====="

  docker compose \
    -f "${compose_file}" \
    config --images \
    | sort -u

  echo
  echo "PASS: Production runtime contract"
}

kafka_runtime() {
  name="hsaai-parity-kafka"

  cleanup() {
    local rc=$?

    if [[ ${rc} -ne 0 ]]; then
      echo
      echo "===== KAFKA FAILURE LOG ====="
      docker logs "${name}" 2>&1 | tail -250 || true
    fi

    docker rm -f "${name}" >/dev/null 2>&1 || true
    exit "${rc}"
  }

  trap cleanup EXIT

  echo "===== KAFKA 7.7.1 RUNTIME PARITY ====="

  docker run -d \
    --name "${name}" \
    -p 9092:9092 \
    -e CLUSTER_ID=MkU3OEVBNTcwNTJENDM2Qk \
    -e KAFKA_NODE_ID=1 \
    -e KAFKA_PROCESS_ROLES=broker,controller \
    -e KAFKA_LISTENERS=PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:29093 \
    -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://localhost:9092 \
    -e KAFKA_CONTROLLER_LISTENER_NAMES=CONTROLLER \
    -e KAFKA_INTER_BROKER_LISTENER_NAME=PLAINTEXT \
    -e KAFKA_LISTENER_SECURITY_PROTOCOL_MAP=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT \
    -e KAFKA_CONTROLLER_QUORUM_VOTERS=1@localhost:29093 \
    -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
    -e KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR=1 \
    -e KAFKA_TRANSACTION_STATE_LOG_MIN_ISR=1 \
    -e KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS=0 \
    confluentinc/cp-kafka:7.7.1

  for attempt in $(seq 1 40); do
    if docker exec "${name}" \
      kafka-topics \
      --bootstrap-server localhost:9092 \
      --list >/dev/null 2>&1; then

      echo "PASS: Kafka broker ready"
      break
    fi

    if [[ "${attempt}" == "40" ]]; then
      echo "ERROR: Kafka did not become ready"
      exit 1
    fi

    echo "Waiting for Kafka (${attempt}/40)"
    sleep 5
  done

  docker exec "${name}" \
    kafka-topics \
    --bootstrap-server localhost:9092 \
    --create \
    --if-not-exists \
    --topic hsaai-production-parity \
    --partitions 1 \
    --replication-factor 1

  printf 'hsaai-production-parity-ok\n' \
    | docker exec -i "${name}" \
        kafka-console-producer \
        --bootstrap-server localhost:9092 \
        --topic hsaai-production-parity

  result="$(
    timeout 30 docker exec "${name}" \
      kafka-console-consumer \
      --bootstrap-server localhost:9092 \
      --topic hsaai-production-parity \
      --from-beginning \
      --max-messages 1
  )"

  echo "${result}"

  echo "${result}" \
    | grep -q "hsaai-production-parity-ok"

  echo "PASS: Kafka 7.7.1 produce/consume parity"
}

mlflow_runtime() {
  name="hsaai-parity-mlflow"

  cleanup() {
    local rc=$?

    if [[ ${rc} -ne 0 ]]; then
      docker logs "${name}" 2>&1 | tail -250 || true
    fi

    docker rm -f "${name}" >/dev/null 2>&1 || true
    exit "${rc}"
  }

  trap cleanup EXIT

  echo "===== MLFLOW 2.18.0 RUNTIME PARITY ====="

  docker run -d \
    --name "${name}" \
    -p 5000:5000 \
    ghcr.io/mlflow/mlflow:v2.18.0 \
    mlflow server \
      --host 0.0.0.0 \
      --port 5000 \
      --workers 1 \
      --backend-store-uri sqlite:////tmp/mlflow.db \
      --default-artifact-root /tmp/mlruns

  wait_http \
    "http://127.0.0.1:5000/health" \
    "MLflow 2.18.0 health" \
    40
}

loki_runtime() {
  name="hsaai-parity-loki"
  config="$(mktemp)"

  cleanup() {
    local rc=$?

    if [[ ${rc} -ne 0 ]]; then
      docker logs "${name}" 2>&1 | tail -250 || true
    fi

    docker rm -f "${name}" >/dev/null 2>&1 || true
    rm -f "${config}"
    exit "${rc}"
  }

  trap cleanup EXIT

  echo "===== LOKI 3.3.2 PRODUCTION CONFIG VALIDATION ====="

  docker run --rm \
    -v "${ROOT}/infrastructure/loki/loki-config.yml:/etc/loki/local-config.yaml:ro" \
    grafana/loki:3.3.2 \
    -config.file=/etc/loki/local-config.yaml \
    -verify-config=true

  echo "PASS: production Loki config validates on 3.3.2"

  cat > "${config}" <<'EOF'
auth_enabled: false

server:
  http_listen_port: 3100

common:
  instance_addr: 127.0.0.1
  path_prefix: /tmp/loki
  storage:
    filesystem:
      chunks_directory: /tmp/loki/chunks
      rules_directory: /tmp/loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2024-01-01
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h
EOF

  chmod 0644 "${config}"

  docker run -d \
    --name "${name}" \
    -p 3100:3100 \
    -v "${config}:/etc/loki/local-config.yaml:ro" \
    grafana/loki:3.3.2 \
    -config.file=/etc/loki/local-config.yaml

  wait_http \
    "http://127.0.0.1:3100/ready" \
    "Loki 3.3.2 runtime" \
    40
}

tempo_runtime() {
  name="hsaai-parity-tempo"
  config="$(mktemp)"

  cleanup() {
    local rc=$?

    if [[ ${rc} -ne 0 ]]; then
      docker logs "${name}" 2>&1 | tail -250 || true
    fi

    docker rm -f "${name}" >/dev/null 2>&1 || true
    rm -f "${config}"
    exit "${rc}"
  }

  trap cleanup EXIT

  echo "===== TEMPO 2.6.0 RUNTIME PARITY ====="

  cat > "${config}" <<'EOF'
server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: 0.0.0.0:4317
        http:
          endpoint: 0.0.0.0:4318

ingester:
  max_block_duration: 5m

compactor:
  compaction:
    block_retention: 1h

storage:
  trace:
    backend: local
    wal:
      path: /tmp/tempo/wal
    local:
      path: /tmp/tempo/blocks
EOF

  docker run --rm \
    grafana/tempo:2.6.0 \
    -version

  chmod 0644 "${config}"

  docker run -d \
    --name "${name}" \
    -p 3200:3200 \
    -v "${config}:/etc/tempo.yaml:ro" \
    grafana/tempo:2.6.0 \
    -config.file=/etc/tempo.yaml

  wait_http \
    "http://127.0.0.1:3200/ready" \
    "Tempo 2.6.0 runtime" \
    40
}

thanos_runtime() {
  name="hsaai-parity-thanos"

  cleanup() {
    local rc=$?

    if [[ ${rc} -ne 0 ]]; then
      docker logs "${name}" 2>&1 | tail -250 || true
    fi

    docker rm -f "${name}" >/dev/null 2>&1 || true
    exit "${rc}"
  }

  trap cleanup EXIT

  echo "===== THANOS 0.37.0 RUNTIME PARITY ====="

  docker run --rm \
    thanosio/thanos:v0.37.0 \
    --version

  docker run -d \
    --name "${name}" \
    -p 10902:10902 \
    thanosio/thanos:v0.37.0 \
    query \
      --http-address=0.0.0.0:10902 \
      --grpc-address=0.0.0.0:10901

  wait_http \
    "http://127.0.0.1:10902/-/healthy" \
    "Thanos 0.37.0 health" \
    40

  wait_http \
    "http://127.0.0.1:10902/-/ready" \
    "Thanos 0.37.0 readiness" \
    20
}

case "${MODE}" in
  contract)
    contract_check
    ;;
  kafka)
    kafka_runtime
    ;;
  mlflow)
    mlflow_runtime
    ;;
  loki)
    loki_runtime
    ;;
  tempo)
    tempo_runtime
    ;;
  thanos)
    thanos_runtime
    ;;
  *)
    echo "ERROR: unsupported parity mode: ${MODE}"
    echo "Valid modes: contract kafka mlflow loki tempo thanos"
    exit 2
    ;;
esac
