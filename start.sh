#!/usr/bin/env bash
# HSAAI Fixed — Production Deployment Script
# ============================================
# Starts the full HSAAI v2.0 stack with all fixes applied.

set -euo pipefail

cd "$(dirname "$0")"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  HSAAI v2.0 — Production Deployment                      ║${NC}"
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
if ! command -v nvidia-smi &>/dev/null; then
    echo -e "${YELLOW}⚠️  No NVIDIA GPU detected. vLLM will fall back to OpenAI API.${NC}"
    echo -e "${YELLOW}   Set VLLM_ENABLED=false in .env to skip vLLM startup.${NC}"
fi

# 4. Pull and build images
echo -e "${GREEN}📦 Building and pulling images...${NC}"
docker compose build --parallel 2>&1 | tail -5
docker compose pull 2>&1 | tail -5

# 5. Start infrastructure first (databases, message bus)
echo -e "${GREEN}🔧 Starting infrastructure services...${NC}"
docker compose up -d postgres qdrant neo4j redis kafka
echo -e "${GREEN}   Waiting 30s for databases to initialize...${NC}"
sleep 30

# 6. Start observability stack
echo -e "${GREEN}📊 Starting observability stack...${NC}"
docker compose up -d otel-collector tempo loki prometheus grafana
sleep 10

# 7. Start identity & security
echo -e "${GREEN}🔐 Starting identity and security services...${NC}"
docker compose up -d keycloak vault opa
sleep 15

# 8. Start LLM gateway
echo -e "${GREEN}🤖 Starting LLM Gateway (vLLM)...${NC}"
docker compose up -d llm-gateway
echo -e "${GREEN}   Waiting 60s for vLLM to load model...${NC}"
sleep 60

# 9. Start application services
echo -e "${GREEN}🚀 Starting application services...${NC}"
docker compose up -d auth-service rag-service agent-runtime alignment-service governance-service api-gateway
sleep 10

# 10. Verify all services
echo -e "${GREEN}✅ Verifying services...${NC}"
echo ""
docker compose ps
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
check_health "Grafana"         "http://localhost:3000/api/health"
check_health "Prometheus"      "http://localhost:9090/-/healthy"
check_health "Loki"            "http://localhost:3100/ready"
check_health "Tempo"           "http://localhost:3200/ready"

echo ""
echo -e "${GREEN}═════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ HSAAI v2.0 Deployment Complete                          ${NC}"
echo -e "${GREEN}═════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "Access points:"
echo -e "  • API Gateway:     http://localhost:8000"
echo -e "  • LLM Gateway:     http://localhost:8090"
echo -e "  • Grafana:         http://localhost:3000  (admin / your GRAFANA_PASSWORD)"
echo -e "  • Keycloak:        http://localhost:8080  (admin / your KEYCLOAK_PASSWORD)"
echo -e "  • Vault:           http://localhost:8200"
echo -e "  • OPA:             http://localhost:8181"
echo ""
echo -e "Next steps:"
echo -e "  1. Verify multi-tenancy: psql -h localhost -U hsaai -d hsaai -c 'SELECT * FROM tenants;'"
echo -e "  2. Test LLM:  curl -X POST http://localhost:8090/v1/generate -H 'Content-Type: application/json' -d '{\"prompt\":\"مرحبا\"}'"
echo -e "  3. View traces: open Grafana → Explore → Tempo"
echo ""
