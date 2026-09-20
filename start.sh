#!/usr/bin/env bash
# HSAAI Fixed — Production Deployment Script
# ============================================
# Starts the full HSAAI v3.0 stack with all verified fixes applied.

set -euo pipefail

cd "$(dirname "$0")"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  HSAAI v3.0 — Full Stack Deployment                      ║${NC}"
echo -e "${GREEN}║  Hayel Saeed Anam Group (HSA Group)                      ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# 1. Check .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  No .env file found. Creating from template.${NC}"
    cp .env.example .env
    echo -e "${RED}❌ Edit .env with your secrets, then re-run this script.${NC}"
    exit 1
fi

# 2. Check Docker
if ! command -v docker &>/dev/null; then
    echo -e "${RED}❌ Docker not installed. Install: https://docs.docker.com/get-docker/${NC}"
    exit 1
fi

if ! docker compose version &>/dev/null; then
    echo -e "${RED}❌ Docker Compose v2 not available.${NC}"
    exit 1
fi

# 3. Check GPU (optional but recommended)
COMPOSE_ARGS=(-f docker-compose.yml)
if command -v nvidia-smi &>/dev/null && docker info 2>/dev/null | grep -qi nvidia; then
    echo -e "${GREEN}✓ NVIDIA GPU runtime detected — enabling Ollama GPU override.${NC}"
    COMPOSE_ARGS+=( -f docker-compose.gpu.yml )
else
    echo -e "${YELLOW}⚠️  NVIDIA container runtime not detected; Ollama will run without the GPU override.${NC}"
fi
DC=(docker compose "${COMPOSE_ARGS[@]}")

# Validate interpolation/references before changing runtime state.
"${DC[@]}" config -q

# 4. Build/pull and start the ENTIRE compose model
echo -e "${GREEN}📦 Building local images...${NC}"
"${DC[@]}" build

echo -e "${GREEN}📥 Pulling external images...${NC}"
"${DC[@]}" pull

echo -e "${GREEN}🚀 Starting all HSAAI services (full stack)...${NC}"
"${DC[@]}" up -d

# 10. Verify all services
echo -e "${GREEN}✅ Verifying services...${NC}"
echo ""
"${DC[@]}" ps
echo ""

# 11. Health checks
echo -e "${GREEN}🩺 Health checks:${NC}"
check_health() {
    local name=$1
    local url=$2
    if curl -sf "$url" >/dev/null 2>&1; then
        echo -e "   ${GREEN}✓${NC} $name — $url"
    else
        echo -e "   ${RED}✗${NC} $name — $url (may still be starting)"
    fi
}

check_health "API Gateway"     "http://localhost:8000/health"
check_health "LLM Gateway"     "http://localhost:8090/health"
check_health "Web"             "http://localhost:3000/"
check_health "Grafana"         "http://localhost:3001/api/health"
check_health "Prometheus"      "http://localhost:9090/-/healthy"
check_health "Loki"            "http://localhost:3100/ready"
check_health "Tempo"           "http://localhost:3200/ready"

echo ""
echo -e "${GREEN}═════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ HSAAI v3.0 Full Stack Deployment Complete                          ${NC}"
echo -e "${GREEN}═════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "Access points:"
echo -e "  • API Gateway:     http://localhost:8000"
echo -e "  • LLM Gateway:     http://localhost:8090"
echo -e "  • Web UI:          http://localhost:3000
  • Grafana:         http://localhost:3001  (admin / your GRAFANA_PASSWORD)"
echo -e "  • Keycloak:        http://localhost:8080  (admin / your KEYCLOAK_ADMIN_PASSWORD)"
echo -e "  • Vault:           http://localhost:8200"
echo -e "  • OPA:             http://localhost:8181"
echo ""
echo -e "Next steps:"
echo -e "  1. Verify multi-tenancy: psql -h localhost -U hsaai -d hsaai -c 'SELECT * FROM tenants;'"
echo -e "  2. Pull the configured Ollama model: docker exec -it \$(docker ps -qf name=ollama) ollama pull qwen2.5:7b-instruct"
echo -e "  3. View traces: open Grafana → Explore → Tempo"
echo ""
