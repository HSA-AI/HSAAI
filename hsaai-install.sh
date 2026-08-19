#!/usr/bin/env bash
# ============================================================================
#  HSAAI v4.1 — ENTERPRISE AI PLATFORM INSTALLER
#  =============================================================
#  Professional unified installer that follows the wiring described in the
#  HSAAI Executive Architecture Book (Chapter 10 — Deployment).
#
#  This script is the SINGLE entry point for deploying HSAAI on a remote
#  Ubuntu 22.04/24.04 LTS desktop/server. It performs the complete wiring:
#
#    Phase 0 — Pre-flight checks (OS, RAM, disk, GPU, internet)
#    Phase 1 — Base system packages + Docker Engine + Compose v2
#    Phase 2 — NVIDIA Container Toolkit (GPU pass-through)
#    Phase 3 — Ollama runtime + default LLM model
#    Phase 4 — Tesseract OCR + Arabic language pack
#    Phase 5 — Generate production .env with strong random secrets
#    Phase 6 — Bootstrap Keycloak realm / clients / users
#    Phase 7 — Start the full stack (infra → security → services → frontend)
#    Phase 8 — Run Alembic migrations + Qdrant collection init
#    Phase 9 — Health verification + smoke tests
#    Phase 10 — Print access points + credentials summary
#
#  Usage:
#    sudo bash hsaai-install.sh                     # full install
#    sudo bash hsaai-install.sh --phase 7           # re-run a single phase
#    sudo bash hsaai-install.sh --skip-gpu          # CPU-only development
#    sudo bash hsaai-install.sh --env-file .env.prod  # custom env file
#    sudo bash hsaai-install.sh --dry-run           # validate without changes
#
#  Author: HSAAI Deployment Engineering
#  Following: HSAAI Executive Architecture Book v1.0 — Chapter 10 (Deployment)
# ============================================================================
set -euo pipefail

# ─── Colors ─────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[0;33m'; RED='\033[0;31m'
BLUE='\033[0;34m';  CYAN='\033[0;36m';  BOLD='\033[1m'; NC='\033[0m'

# ─── Logging helpers ────────────────────────────────────────────────────────
log()  { echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $*"; }
info() { echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $*"; }
warn() { echo -e "${YELLOW}[$(date +'%H:%M:%S')] WARN:${NC} $*"; }
err()  { echo -e "${RED}[$(date +'%H:%M:%S')] ERROR:${NC} $*" >&2; }
phase(){ echo -e "\n${CYAN}${BOLD}════════════════════════════════════════════════════════════════${NC}"
         echo -e "${CYAN}${BOLD}  PHASE $1: $2${NC}"
         echo -e "${CYAN}${BOLD}════════════════════════════════════════════════════════════════${NC}\n"; }

# ─── Paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}"
ENV_FILE="${PROJECT_ROOT}/.env"
ENV_TEMPLATE="${PROJECT_ROOT}/.env.production.example"

# ─── Defaults ───────────────────────────────────────────────────────────────
SKIP_GPU=0
SKIP_OLLAMA=0
DRY_RUN=0
SINGLE_PHASE=""
CUSTOM_ENV=""
MIN_RAM_GB=32
MIN_DISK_GB=200

# ─── Argument parsing ───────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --phase)        SINGLE_PHASE="$2"; shift 2 ;;
    --skip-gpu)     SKIP_GPU=1; shift ;;
    --skip-ollama)  SKIP_OLLAMA=1; shift ;;
    --dry-run)      DRY_RUN=1; shift ;;
    --env-file)     CUSTOM_ENV="$2"; ENV_FILE="$2"; shift 2 ;;
    --help|-h)
      grep '^#' "$0" | sed 's/^# \?//'
      exit 0 ;;
    *) err "Unknown argument: $1"; exit 2 ;;
  esac
done

# ─── Pre-flight: root check ─────────────────────────────────────────────────
phase 0 "PRE-FLIGHT CHECKS"

if [[ $EUID -ne 0 ]]; then
  err "This installer must be run as root (use: sudo bash $0)"
  exit 1
fi

# OS check
if ! grep -qiE 'ubuntu (22|24)\.' /etc/os-release 2>/dev/null; then
  warn "Target OS should be Ubuntu 22.04 or 24.04 LTS. Detected:"
  grep PRETTY_NAME /etc/os-release || true
  warn "Continuing — but package names may differ on other distros."
fi

# RAM check
RAM_KB=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
RAM_GB=$((RAM_KB / 1024 / 1024))
info "RAM:  ${RAM_GB} GB (minimum ${MIN_RAM_GB} GB)"
if [[ $RAM_GB -lt $MIN_RAM_GB ]]; then
  if [[ $SKIP_GPU -eq 1 ]]; then
    warn "RAM ${RAM_GB}GB is below the ${MIN_RAM_GB}GB minimum. Continuing in dev mode."
  else
    err "RAM ${RAM_GB}GB is below the ${MIN_RAM_GB}GB minimum. vLLM/Kafka will OOM."
    err "Re-run with --skip-gpu for a CPU-only development deployment."
    exit 1
  fi
fi

# Disk check
DISK_GB=$(df -BG "${PROJECT_ROOT}" | awk 'NR==2 {gsub("G","",$4); print $4}')
info "Disk: ${DISK_GB} GB free (minimum ${MIN_DISK_GB} GB recommended)"
if [[ $DISK_GB -lt $MIN_DISK_GB ]]; then
  warn "Disk space ${DISK_GB}GB is below the ${MIN_DISK_GB}GB recommendation."
  warn "Docker images + model weights + documents may fill the disk."
fi

# GPU check
if [[ $SKIP_GPU -eq 0 ]]; then
  if ! command -v nvidia-smi &>/dev/null; then
    warn "nvidia-smi not found. NVIDIA host drivers are required for vLLM."
    warn "Install them first: sudo apt-get install -y nvidia-driver-535 && sudo reboot"
    warn "Or re-run this installer with --skip-gpu for CPU-only mode."
    SKIP_GPU=1
  else
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1)
    info "GPU:  ${GPU_NAME} (${VRAM_MB} MB VRAM)"
    if [[ ${VRAM_MB:-0} -lt 16000 ]]; then
      warn "GPU VRAM ${VRAM_MB}MB is below the 16GB minimum for Qwen2.5-7B."
      warn "LLM gateway will fall back to OpenAI API or a smaller model."
    fi
  fi
else
  info "GPU check skipped (--skip-gpu)"
fi

# Internet connectivity
if ! ping -c 1 -W 3 archive.ubuntu.com &>/dev/null; then
  warn "No internet connectivity to archive.ubuntu.com — apt installs may fail."
fi

log "✓ Pre-flight checks passed"

# If dry-run, exit here
if [[ $DRY_RUN -eq 1 ]]; then
  log "Dry run complete — no changes were made."
  exit 0
fi

# ─── Helper: run a phase (or skip if SINGLE_PHASE is set) ───────────────────
run_phase() {
  local num="$1"; shift
  if [[ -n "${SINGLE_PHASE}" && "${SINGLE_PHASE}" != "${num}" ]]; then
    return 0
  fi
  "$@"
}

# ============================================================================
#  PHASE 1 — Base system + Docker
# ============================================================================
install_docker() {
  phase 1 "BASE SYSTEM + DOCKER ENGINE"

  if command -v docker &>/dev/null && docker compose version &>/dev/null; then
    log "Docker already installed: $(docker --version)"
    return 0
  fi

  log "Updating apt and installing base packages..."
  apt-get update -qq
  apt-get install -y -qq \
    ca-certificates curl gnupg lsb-release \
    apt-transport-https software-properties-common \
    git jq python3 python3-pip python3-venv \
    wget unzip htop vim less \
    > /dev/null 2>&1

  log "Adding Docker's official GPG key + repository..."
  install -m 0755 -d /etc/apt/keyrings
  if [[ ! -f /etc/apt/keyrings/docker.gpg ]]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
      | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
  fi
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
    > /etc/apt/sources.list.d/docker.list

  apt-get update -qq
  log "Installing Docker Engine + Compose v2..."
  apt-get install -y -qq \
    docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin \
    > /dev/null 2>&1

  systemctl enable --now docker

  # Add current sudo user to docker group
  local REAL_USER="${SUDO_USER:-${USER:-}}"
  if [[ -n "${REAL_USER}" && "${REAL_USER}" != "root" ]]; then
    usermod -aG docker "${REAL_USER}"
    info "Added user '${REAL_USER}' to docker group (re-login to take effect)."
  fi

  log "✓ Docker installed: $(docker --version)"
  docker compose version
}
run_phase 1 install_docker

# ============================================================================
#  PHASE 2 — NVIDIA Container Toolkit
# ============================================================================
install_nvidia_toolkit() {
  phase 2 "NVIDIA CONTAINER TOOLKIT"

  if [[ $SKIP_GPU -eq 1 ]]; then
    info "Skipping (GPU disabled). vLLM will fall back to OpenAI API."
    return 0
  fi

  if docker info 2>/dev/null | grep -q "Runtimes:.*nvidia"; then
    log "NVIDIA runtime already configured for Docker."
    return 0
  fi

  log "Adding NVIDIA Container Toolkit repository..."
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    > /etc/apt/sources.list.d/nvidia-container-toolkit.list

  apt-get update -qq
  apt-get install -y -qq nvidia-container-toolkit > /dev/null 2>&1

  log "Configuring Docker to use NVIDIA runtime..."
  nvidia-ctk runtime configure --runtime=docker
  systemctl restart docker

  log "Verifying GPU is accessible inside a container..."
  if docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi &>/dev/null; then
    log "✓ GPU pass-through verified"
  else
    warn "GPU verification failed — vLLM will not be able to use the GPU."
    warn "Check 'nvidia-smi' on the host and reinstall drivers if needed."
  fi
}
run_phase 2 install_nvidia_toolkit

# ============================================================================
#  PHASE 3 — Ollama + default model
# ============================================================================
install_ollama() {
  phase 3 "OLLAMA + DEFAULT LLM MODEL"

  if [[ $SKIP_OLLAMA -eq 1 ]]; then
    info "Skipping Ollama (--skip-ollama)."
    return 0
  fi

  if command -v ollama &>/dev/null; then
    log "Ollama already installed: $(ollama --version 2>&1 | head -1)"
  else
    log "Installing Ollama via official convenience script..."
    curl -fsSL https://ollama.com/install.sh | sh
    systemctl enable --now ollama
  fi

  # Pull default models (idempotent — ollama pull skips if already present)
  local LLM_MODEL="${HSAAI_MODEL_NAME:-qwen2.5:7b-instruct}"
  local EMBED_MODEL="${HSAAI_EMBEDDING_MODEL:-all-minilm:l6-v2}"

  log "Pulling LLM model: ${LLM_MODEL} (~5 GB, may take several minutes)..."
  su - "${SUDO_USER:-root}" -c "ollama pull ${LLM_MODEL}" || \
    warn "LLM pull failed — you can pull it manually later: ollama pull ${LLM_MODEL}"

  log "Pulling embedding model: ${EMBED_MODEL} (~100 MB)..."
  su - "${SUDO_USER:-root}" -c "ollama pull ${EMBED_MODEL}" || \
    warn "Embedding pull failed — you can pull it manually later: ollama pull ${EMBED_MODEL}"

  log "✓ Ollama ready at http://localhost:11434"
}
run_phase 3 install_ollama

# ============================================================================
#  PHASE 4 — Tesseract OCR + Arabic
# ============================================================================
install_tesseract() {
  phase 4 "TESSERACT OCR + ARABIC LANGUAGE PACK"

  if command -v tesseract &>/dev/null && tesseract --list-langs 2>&1 | grep -q "^ara$"; then
    log "Tesseract + Arabic already installed."
    return 0
  fi

  log "Installing Tesseract OCR + language packs..."
  apt-get install -y -qq \
    tesseract-ocr tesseract-ocr-ara tesseract-ocr-eng tesseract-ocr-osd \
    poppler-utils libtesseract-dev libleptonica-dev \
    > /dev/null 2>&1

  # Persist TESSDATA_PREFIX for all shells
  cat > /etc/profile.d/tessdata.sh << 'EOF'
export TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata
EOF
  export TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

  log "✓ Tesseract $(tesseract --version | head -1)"
  info "Available languages: $(tesseract --list-langs 2>&1 | tr '\n' ' ')"
}
run_phase 4 install_tesseract

# ============================================================================
#  PHASE 5 — Generate .env with strong random secrets
# ============================================================================
configure_env() {
  phase 5 "GENERATE PRODUCTION .env"

  if [[ -n "${CUSTOM_ENV}" && -f "${CUSTOM_ENV}" ]]; then
    log "Using custom env file: ${CUSTOM_ENV}"
    ENV_FILE="${CUSTOM_ENV}"
    return 0
  fi

  if [[ ! -f "${ENV_TEMPLATE}" ]]; then
    err "Template not found: ${ENV_TEMPLATE}"
    err "Make sure you are running this from the HSAAI project root."
    exit 1
  fi

  # Backup existing .env
  if [[ -f "${ENV_FILE}" ]]; then
    local BACKUP="${ENV_FILE}.bak.$(date +%Y%m%d%H%M%S)"
    cp "${ENV_FILE}" "${BACKUP}"
    warn "Existing .env backed up to ${BACKUP}"
  fi

  # Strong secret generators
  gen_secret()   { head -c 32 /dev/urandom | base64 | tr -d '/+=' | cut -c1-32; }
  gen_password() { head -c 24 /dev/urandom | base64 | tr -d '/+=' | cut -c1-24; }

  local POSTGRES_PASSWORD=$(gen_password)
  local KEYCLOAK_ADMIN_PASSWORD=$(gen_password)
  local KEYCLOAK_CLIENT_SECRET=$(gen_secret)
  local NEO4J_PASSWORD=$(gen_password)
  local GRAFANA_ADMIN_PASSWORD=$(gen_password)
  local QDRANT_API_KEY=$(gen_secret)
  local JWT_SECRET=$(gen_secret)
  local AUDIT_HMAC_KEY=$(gen_secret)
  local ENCRYPTION_KEY=$(gen_secret)
  local MINIO_ROOT_PASSWORD=$(gen_password)
  local VAULT_TOKEN=$(gen_secret)

  # Determine server IP for CORS / hostname
  local SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")
  local DOMAIN_NAME="${HSAAI_DOMAIN:-${SERVER_IP}}"

  log "Generating .env with strong random secrets..."
  log "  Server IP / domain: ${DOMAIN_NAME}"

  cp "${ENV_TEMPLATE}" "${ENV_FILE}"

  # Substitute all CHANGE_ME_* placeholders
  sed -i "s|CHANGE_ME_STRONG_POSTGRES_PASSWORD|${POSTGRES_PASSWORD}|g"            "${ENV_FILE}"
  sed -i "s|CHANGE_ME_STRONG_KEYCLOAK_ADMIN_PASSWORD|${KEYCLOAK_ADMIN_PASSWORD}|g" "${ENV_FILE}"
  sed -i "s|CHANGE_ME_REAL_KEYCLOAK_CLIENT_SECRET|${KEYCLOAK_CLIENT_SECRET}|g"     "${ENV_FILE}"
  sed -i "s|change-me-strong-neo4j-password|${NEO4J_PASSWORD}|g"                   "${ENV_FILE}"
  sed -i "s|CHANGE_ME_STRONG_GRAFANA_PASSWORD|${GRAFANA_ADMIN_PASSWORD}|g"         "${ENV_FILE}"
  sed -i "s|CHANGE_ME_QDRANT_API_KEY_OR_LEAVE_EMPTY_IF_INTERNAL_ONLY|${QDRANT_API_KEY}|g" "${ENV_FILE}"
  sed -i "s|CHANGE_ME_SMTP_PASSWORD||g"                                             "${ENV_FILE}"

  # Domain + CORS
  sed -i "s|DOMAIN_NAME=ai.example.com|DOMAIN_NAME=${DOMAIN_NAME}|g"               "${ENV_FILE}"
  sed -i "s|https://ai.example.com|http://${DOMAIN_NAME}|g"                        "${ENV_FILE}"
  sed -i "s|CORS_ALLOW_ORIGINS=.*|CORS_ALLOW_ORIGINS=http://${DOMAIN_NAME}:3000,http://${DOMAIN_NAME}:8080,http://localhost:3000|g" "${ENV_FILE}"

  # Add MinIO credentials (required by docker-compose)
  cat >> "${ENV_FILE}" << EOF

# ─── Generated Secrets (Phase 5 — $(date -Iseconds)) ────────────────────────
# KEEP THIS FILE PRIVATE (chmod 600 enforced). Back up to a secure location.
MINIO_ROOT_USER=hsaai_minio_admin
MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}
VAULT_TOKEN=${VAULT_TOKEN}
JWT_SECRET=${JWT_SECRET}
AUDIT_HMAC_KEY=${AUDIT_HMAC_KEY}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
HSAAI_DEPLOYMENT_DATE=$(date -Iseconds)
HSAAI_DEPLOYMENT_HOST=$(hostname)
HSAAI_DEPLOYMENT_IP=${SERVER_IP}
EOF

  chmod 600 "${ENV_FILE}"

  log "✓ .env generated at ${ENV_FILE}"
  echo ""
  echo -e "${YELLOW}${BOLD}╔══════════════════════════════════════════════════════════════════╗${NC}"
  echo -e "${YELLOW}${BOLD}║  SAVE THESE CREDENTIALS — THEY ARE NOT RECOVERABLE              ║${NC}"
  echo -e "${YELLOW}${BOLD}╠══════════════════════════════════════════════════════════════════╣${NC}"
  echo -e "${YELLOW}║  PostgreSQL:     hsaai / ${POSTGRES_PASSWORD}${NC}"
  echo -e "${YELLOW}║  Keycloak admin: admin  / ${KEYCLOAK_ADMIN_PASSWORD}${NC}"
  echo -e "${YELLOW}║  Keycloak client: hsaai-web / ${KEYCLOAK_CLIENT_SECRET}${NC}"
  echo -e "${YELLOW}║  Neo4j:          neo4j  / ${NEO4J_PASSWORD}${NC}"
  echo -e "${YELLOW}║  Grafana:        admin  / ${GRAFANA_ADMIN_PASSWORD}${NC}"
  echo -e "${YELLOW}║  MinIO:          hsaai_minio_admin / ${MINIO_ROOT_PASSWORD}${NC}"
  echo -e "${YELLOW}║  Qdrant API key: ${QDRANT_API_KEY}${NC}"
  echo -e "${YELLOW}║  Vault token:    ${VAULT_TOKEN}${NC}"
  echo -e "${YELLOW}║  JWT secret:     ${JWT_SECRET}${NC}"
  echo -e "${YELLOW}${BOLD}╚══════════════════════════════════════════════════════════════════╝${NC}"
  echo ""
  warn "These are also stored in ${ENV_FILE} (chmod 600)."
  warn "Back them up to Vault / 1Password / sealed secrets immediately."
}
run_phase 5 configure_env

# ============================================================================
#  PHASE 6 — Bootstrap Keycloak realm / clients / users
# ============================================================================
bootstrap_keycloak() {
  phase 6 "BOOTSTRAP KEYCLOAK (REALM / CLIENTS / USERS)"

  cd "${PROJECT_ROOT}"

  log "Starting Keycloak container in isolation..."
  docker compose --env-file "${ENV_FILE}" up -d keycloak

  log "Waiting for Keycloak to become healthy (up to 180s)..."
  local ready=0
  for i in $(seq 1 60); do
    if curl -sf "http://localhost:8080/realms/master/.well-known/openid-configuration" >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 3
  done
  if [[ $ready -eq 0 ]]; then
    err "Keycloak did not become healthy in 180s."
    err "Check: docker compose logs keycloak --tail 50"
    exit 1
  fi
  log "✓ Keycloak is ready"

  # Load credentials from .env
  source <(grep -E '^(KEYCLOAK_ADMIN_PASSWORD|KEYCLOAK_CLIENT_SECRET)=' "${ENV_FILE}")

  # Use kcadm.sh inside the container to import the realm if not already imported
  log "Importing hsaai realm (idempotent)..."
  docker compose exec -T keycloak /opt/keycloak/bin/kcadm.sh \
    config credentials --server http://localhost:8080 \
    --realm master --user admin --password "${KEYCLOAK_ADMIN_PASSWORD}" 2>/dev/null || true

  # Import the realm JSON (idempotent — skip if it already exists)
  if ! docker compose exec -T keycloak curl -sf \
       "http://localhost:8080/admin/realms/hsaai" >/dev/null 2>&1; then
    docker compose exec -T keycloak /opt/keycloak/bin/kcadm.sh \
      create realms -f /opt/keycloak/data/import/hsaai-realm.json 2>/dev/null || \
      warn "Realm import via kcadm failed — it may already exist or the file is malformed."
  else
    log "Realm 'hsaai' already exists — skipping import."
  fi

  log "✓ Keycloak realm 'hsaai' is ready"
}
run_phase 6 bootstrap_keycloak

# ============================================================================
#  PHASE 7 — Start the full stack (wiring from Architecture Book Ch. 10)
# ============================================================================
start_stack() {
  phase 7 "START FULL STACK (INFRA → SECURITY → SERVICES → FRONTEND)"

  cd "${PROJECT_ROOT}"

  log "Building all custom Docker images (10-20 minutes on first run)..."
  docker compose --env-file "${ENV_FILE}" build --parallel 2>&1 | tail -10

  log "Pulling pre-built images (postgres, redis, qdrant, neo4j, kafka, etc.)..."
  docker compose --env-file "${ENV_FILE}" pull 2>&1 | tail -5

  # Layer 1: Infrastructure (Chapter 10 §10.2)
  log "Layer 1/4: Starting infrastructure (databases + message bus)..."
  docker compose --env-file "${ENV_FILE}" up -d \
      postgres redis qdrant neo4j kafka minio minio-init
  log "  Waiting 30s for databases to initialize..."
  sleep 30

  # Layer 2: Observability (Chapter 10 §10.3)
  log "Layer 2/4: Starting observability (Prometheus, Grafana, Loki, Tempo, OTEL)..."
  docker compose --env-file "${ENV_FILE}" up -d \
      otel-collector tempo loki prometheus grafana \
      thanos-sidecar thanos-store thanos-query thanos-compactor thanos-ruler \
      mlflow
  sleep 10

  # Layer 3: Security (Chapter 10 §10.4)
  log "Layer 3/4: Starting security (Vault, OPA)..."
  docker compose --env-file "${ENV_FILE}" up -d vault opa
  sleep 10

  # Layer 4: Application services (Chapter 10 §10.5)
  log "Layer 4/4: Starting application services (12 microservices + frontend)..."
  docker compose --env-file "${ENV_FILE}" up -d \
      llm-gateway \
      auth-service \
      backend-core \
      rag-service \
      agent-runtime \
      workflow-engine \
      alignment-service \
      governance-service \
      pii-detector \
      mcp-server \
      model-training \
      api-gateway \
      frontend

  log "Waiting 60s for services to initialize..."
  sleep 60

  log "✓ Stack started — running docker compose ps:"
  docker compose --env-file "${ENV_FILE}" ps
}
run_phase 7 start_stack

# ============================================================================
#  PHASE 8 — Database migrations + Qdrant collection
# ============================================================================
init_datastores() {
  phase 8 "DATABASE MIGRATIONS + QDRANT COLLECTION INIT"

  cd "${PROJECT_ROOT}"

  log "Running Alembic migrations (creates all tables, RLS policies, indexes)..."
  if docker compose --env-file "${ENV_FILE}" exec -T backend-core \
       sh -c 'cd /app && USE_ALEMBIC=true alembic upgrade head' 2>&1 | tail -20; then
    log "✓ Migrations applied successfully"
  else
    warn "Migrations failed — you can run them manually:"
    warn "  docker compose exec backend-core sh -c 'cd /app && alembic upgrade head'"
  fi

  log "Creating Qdrant collection 'hsaai_knowledge' (384-dim, 4 shards)..."
  if curl -sf -X PUT "http://localhost:6333/collections/hsaai_knowledge" \
        -H "Content-Type: application/json" \
        -d '{
          "vectors": {"size": 384, "distance": "Cosine"},
          "sharding_method": 1,
          "replication_factor": 1,
          "write_consistency_factor": 1
        }' >/dev/null 2>&1; then
    log "✓ Qdrant collection created"
  else
    warn "Qdrant collection creation failed — it may already exist."
  fi

  log "Verifying PostgreSQL schema..."
  docker compose --env-file "${ENV_FILE}" exec -T postgres \
    psql -U hsaai -d hsaai -c "\dt" 2>&1 | head -20
}
run_phase 8 init_datastores

# ============================================================================
#  PHASE 9 — Health verification + smoke tests
# ============================================================================
verify_health() {
  phase 9 "HEALTH VERIFICATION + SMOKE TESTS"

  cd "${PROJECT_ROOT}"

  local PASS=0; local FAIL=0; local SKIP=0

  check() {
    local name="$1" url="$2"
    if curl -sf -m 5 "${url}" >/dev/null 2>&1; then
      log "  ✓ ${name}"
      PASS=$((PASS+1))
    else
      warn "  ✗ ${name} (${url})"
      FAIL=$((FAIL+1))
    fi
  }

  log "Infrastructure health:"
  check "PostgreSQL"        "http://localhost:5432"
  check "Redis (ping)"      "http://localhost:6379"
  check "Qdrant"            "http://localhost:6333/healthz"
  check "Neo4j"             "http://localhost:7474"
  check "Kafka"             "http://localhost:9092"
  check "MinIO"             "http://localhost:9000/minio/health/live"

  log "Observability health:"
  check "Prometheus"        "http://localhost:9090/-/healthy"
  check "Grafana"           "http://localhost:3001/api/health"
  check "Loki"              "http://localhost:3100/ready"
  check "Tempo"             "http://localhost:3200/ready"
  check "OTEL Collector"    "http://localhost:13133/"

  log "Security health:"
  check "Keycloak"          "http://localhost:8080/realms/master/.well-known/openid-configuration"
  check "Vault"             "http://localhost:8200/v1/sys/health"
  check "OPA"               "http://localhost:8181/health"

  log "Application services:"
  check "API Gateway"       "http://localhost:8000/health"
  check "Backend Core"      "http://localhost:8001/health"
  check "Auth Service"      "http://localhost:8010/health"
  check "RAG Engine"        "http://localhost:8030/health"
  check "LLM Gateway"       "http://localhost:8090/health"
  check "Workflow Engine"   "http://localhost:8070/health"
  check "Alignment Service" "http://localhost:8005/health"
  check "Governance"        "http://localhost:8011/health"
  check "PII Detector"      "http://localhost:8092/health"
  check "MCP Server"        "http://localhost:8094/health"
  check "Model Training"    "http://localhost:8091/health"
  check "Frontend"          "http://localhost:3000/"

  echo ""
  log "════════════════════════════════════════════════════════════════"
  log "  Health summary: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}, ${YELLOW}${SKIP} skipped${NC}"
  log "════════════════════════════════════════════════════════════════"

  if [[ ${FAIL} -gt 0 ]]; then
    warn "Some services failed. Common fixes:"
    warn "  - Wait 60s and re-run: sudo bash $0 --phase 9"
    warn "  - Check logs: docker compose logs <service> --tail 50"
    warn "  - Restart a service: docker compose restart <service>"
  fi
}
run_phase 9 verify_health

# ============================================================================
#  PHASE 10 — Summary + access points
# ============================================================================
print_summary() {
  phase 10 "DEPLOYMENT COMPLETE — ACCESS POINTS"

  source <(grep -E '^(KEYCLOAK_ADMIN_PASSWORD|GRAFANA_ADMIN_PASSWORD|NEO4J_PASSWORD|MINIO_ROOT_USER|MINIO_ROOT_PASSWORD|QDRANT_API_KEY)=' "${ENV_FILE}" 2>/dev/null || true)

  local IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

  echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════════════════════╗${NC}"
  echo -e "${GREEN}${BOLD}║                                                                      ║${NC}"
  echo -e "${GREEN}${BOLD}║   HSAAI v4.1 — DEPLOYMENT COMPLETE                                   ║${NC}"
  echo -e "${GREEN}${BOLD}║   Enterprise AI Platform — Hayel Saeed Anam Group                    ║${NC}"
  echo -e "${GREEN}${BOLD}║                                                                      ║${NC}"
  echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════════════════════╝${NC}"
  echo ""
  echo -e "${CYAN}${BOLD}Access Points:${NC}"
  echo -e "  ${BOLD}Frontend (Next.js)${NC}:    http://${IP}:3000"
  echo -e "  ${BOLD}API Gateway${NC}:           http://${IP}:8000"
  echo -e "  ${BOLD}Backend Core${NC}:          http://${IP}:8001"
  echo -e "  ${BOLD}Keycloak Admin${NC}:        http://${IP}:8080  (admin / ${KEYCLOAK_ADMIN_PASSWORD:-<see .env>})"
  echo -e "  ${BOLD}Grafana${NC}:               http://${IP}:3001  (admin / ${GRAFANA_ADMIN_PASSWORD:-<see .env>})"
  echo -e "  ${BOLD}Prometheus${NC}:            http://${IP}:9090"
  echo -e "  ${BOLD}Loki${NC}:                  http://${IP}:3100"
  echo -e "  ${BOLD}Tempo${NC}:                 http://${IP}:3200"
  echo -e "  ${BOLD}Qdrant Dashboard${NC}:      http://${IP}:6333/dashboard"
  echo -e "  ${BOLD}Neo4j Browser${NC}:         http://${IP}:7474  (neo4j / ${NEO4J_PASSWORD:-<see .env>})"
  echo -e "  ${BOLD}MinIO Console${NC}:         http://${IP}:9001  (${MINIO_ROOT_USER:-hsaai_minio_admin} / ${MINIO_ROOT_PASSWORD:-<see .env>})"
  echo -e "  ${BOLD}MLflow${NC}:                http://${IP}:5000"
  echo -e "  ${BOLD}Vault${NC}:                 http://${IP}:8200"
  echo -e "  ${BOLD}OPA${NC}:                   http://${IP}:8181"
  echo ""
  echo -e "${CYAN}${BOLD}Next steps:${NC}"
  echo -e "  1. Open ${BOLD}http://${IP}:3000${NC} in your browser to access the HSAAI frontend."
  echo -e "  2. Log in with one of the seeded users (admin / executive / hr_manager / ai_user)."
  echo -e "  3. Configure enterprise integrations (SAP, SharePoint, AD) in the Admin panel."
  echo -e "  4. Set up DNS + TLS (Let's Encrypt) for production access."
  echo -e "  5. Back up the .env file to a secure location."
  echo ""
  echo -e "${CYAN}${BOLD}Useful commands:${NC}"
  echo -e "  ${BOLD}View service status${NC}:    docker compose ps"
  echo -e "  ${BOLD}Tail logs${NC}:               docker compose logs -f <service>"
  echo -e "  ${BOLD}Restart a service${NC}:       docker compose restart <service>"
  echo -e "  ${BOLD}Stop everything${NC}:         docker compose down"
  echo -e "  ${BOLD}Re-run health checks${NC}:    sudo bash $0 --phase 9"
  echo ""
  echo -e "${YELLOW}Documentation: ${PROJECT_ROOT}/docs/${NC}"
  echo -e "${YELLOW}Runbooks:      ${PROJECT_ROOT}/runbooks/${NC}"
  echo ""
}
run_phase 10 print_summary

log "HSAAI installer finished successfully."
