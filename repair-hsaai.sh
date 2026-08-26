#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "============================================================"
echo " HSAAI MASTER REPAIR"
echo "============================================================"

timestamp="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR=".repair-backup/$timestamp"

mkdir -p "$BACKUP_DIR"

backup_file() {
    local f="$1"
    if [[ -f "$f" ]]; then
        mkdir -p "$BACKUP_DIR/$(dirname "$f")"
        cp -a "$f" "$BACKUP_DIR/$f"
        echo "[BACKUP] $f"
    fi
}

echo
echo "[1/10] Backing up important files..."

backup_file "services/backend_core/core/engine.py"
backup_file "services/multi_agents/main.py"
backup_file "infrastructure/docker/docker-compose.production.yml"
backup_file "infrastructure/docker/docker-compose.dev.yml"
backup_file "scripts/deploy-production.sh"
backup_file ".env.production"
backup_file ".env.production.example"

echo
echo "[2/10] Checking project structure..."

mkdir -p \
    services/ai_orchestrator \
    infrastructure/docker \
    scripts

echo
echo "[3/10] Creating AI Orchestrator compatibility service..."

cat > services/ai_orchestrator/Dockerfile <<'EOF'
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    httpx \
    pydantic

COPY services/ai_orchestrator/main.py /app/main.py

RUN useradd \
    --create-home \
    --uid 1000 \
    appuser

USER appuser

EXPOSE 8020

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8020"]
EOF

cat > services/ai_orchestrator/main.py <<'PY'
import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(
    title="HSAAI AI Orchestrator Compatibility Service",
    version="1.0.0",
)


MULTI_AGENTS_URL = os.getenv(
    "MULTI_AGENTS_URL",
    "http://multi_agents:8040",
).rstrip("/")


class OrchestrateRequest(BaseModel):
    message: str
    tenant_id: str = "default"
    workspace_id: str = "default"

    preferred_agent: str | None = None
    task: str | None = None

    context: str = ""
    system_prompt: str | None = None

    knowledge_scopes: list[str] = Field(default_factory=list)

    user_id: str | None = None
    claims: dict[str, Any] = Field(default_factory=dict)

    metadata: dict[str, Any] = Field(default_factory=dict)


def build_multi_agents_payload(
    request: OrchestrateRequest,
) -> dict[str, Any]:
    """
    Keep the adapter deliberately permissive.

    multi_agents implementations can evolve without requiring
    backend_core to know the internal schema.
    """

    return {
        "message": request.message,
        "tenant_id": request.tenant_id,
        "workspace_id": request.workspace_id,
        "preferred_agent": request.preferred_agent,
        "agent": request.preferred_agent,
        "task": request.task,
        "context": request.context,
        "system_prompt": request.system_prompt,
        "knowledge_scopes": request.knowledge_scopes,
        "user_id": request.user_id,
        "claims": request.claims,
        "metadata": request.metadata,
    }


def normalize_response(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        response = (
            data.get("response")
            or data.get("answer")
            or data.get("output")
            or data.get("result")
            or ""
        )

        result = dict(data)

        if response and "response" not in result:
            result["response"] = response

        return result

    if isinstance(data, str):
        return {
            "response": data,
        }

    return {
        "response": str(data),
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    multi_agents_status = "unknown"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{MULTI_AGENTS_URL}/health")

            if r.status_code < 400:
                multi_agents_status = "healthy"
            else:
                multi_agents_status = "unhealthy"

    except Exception:
        multi_agents_status = "unreachable"

    return {
        "status": "ok",
        "service": "ai_orchestrator",
        "multi_agents_url": MULTI_AGENTS_URL,
        "multi_agents_status": multi_agents_status,
    }


@app.get("/ready")
async def ready() -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{MULTI_AGENTS_URL}/health")

        if r.status_code >= 400:
            raise HTTPException(
                status_code=503,
                detail="multi_agents is unhealthy",
            )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"multi_agents unavailable: {exc}",
        )

    return {
        "status": "ready",
        "service": "ai_orchestrator",
    }


@app.post("/orchestrate")
async def orchestrate(request: OrchestrateRequest) -> dict[str, Any]:
    payload = build_multi_agents_payload(request)

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{MULTI_AGENTS_URL}/v1/run",
                json=payload,
            )

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="multi_agents request timed out",
        )

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"multi_agents unavailable: {exc}",
        )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.text[:1000],
        )

    try:
        data = response.json()
    except Exception:
        data = response.text

    result = normalize_response(data)

    result.setdefault(
        "orchestrator",
        "ai_orchestrator",
    )

    result.setdefault(
        "multi_agents_url",
        MULTI_AGENTS_URL,
    )

    return result
PY

cat > services/ai_orchestrator/requirements.txt <<'EOF'
fastapi
uvicorn[standard]
httpx
pydantic
EOF

echo "[OK] AI Orchestrator compatibility service created."

echo
echo "[4/10] Fixing backend orchestrator default..."

python - <<'PY'
from pathlib import Path

p = Path("services/backend_core/core/engine.py")

if p.exists():
    s = p.read_text()

    old = 'http://ai_orchestrator:8020'
    new = 'http://ai_orchestrator:8020'

    # Keep the compatibility endpoint at 8020.
    # This intentionally does NOT break existing backend_core logic.
    s = s.replace(
        'AI_ORCHESTRATOR_URL = os.getenv("AI_ORCHESTRATOR_URL", "http://ai_orchestrator:8020")',
        'AI_ORCHESTRATOR_URL = os.getenv("AI_ORCHESTRATOR_URL", "http://ai_orchestrator:8020")',
    )

    p.write_text(s)

    print("[OK] backend_core orchestrator contract preserved.")
else:
    print("[WARN] backend_core/core/engine.py not found.")
PY

echo
echo "[5/10] Creating production environment template..."

cat > .env.production.example <<'EOF'
# ============================================================
# HSAAI PRODUCTION ENVIRONMENT
# ============================================================

# Application
APP_ENV=production
ENVIRONMENT=production

# Security
JWT_SECRET=CHANGE_ME
DATA_ENCRYPTION_KEY=CHANGE_ME

# PostgreSQL
POSTGRES_DB=hsai
POSTGRES_USER=hsai
POSTGRES_PASSWORD=CHANGE_ME

# Redis
REDIS_PASSWORD=CHANGE_ME

# Neo4j
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=CHANGE_ME

# Elasticsearch
ELASTIC_PASSWORD=CHANGE_ME

# Keycloak
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=CHANGE_ME

# AI services
AI_ORCHESTRATOR_URL=http://ai_orchestrator:8020
MULTI_AGENTS_URL=http://multi_agents:8040
RAG_ENGINE_URL=http://rag_engine:8030

# Analytics
ANALYTICS_URL=http://backend:8000

# Security defaults
INTERNAL_ONLY_MODE=true
ALLOW_EXTERNAL_APIS=false
STRICT_EGRESS_DENY=true
EOF

echo "[OK] .env.production.example created."

echo
echo "[6/10] Creating secure environment generator..."

cat > scripts/generate-production-env.sh <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ENV_FILE=".env.production"

if [[ -f "$ENV_FILE" ]]; then
    echo "ERROR: $ENV_FILE already exists."
    echo "Refusing to overwrite production secrets."
    exit 1
fi

rand_hex() {
    openssl rand -hex 32
}

rand_b64() {
    openssl rand -base64 48 | tr -d '\n'
}

cat > "$ENV_FILE" <<ENV
APP_ENV=production
ENVIRONMENT=production

JWT_SECRET=$(rand_hex)
DATA_ENCRYPTION_KEY=$(rand_b64)

POSTGRES_DB=hsai
POSTGRES_USER=hsai
POSTGRES_PASSWORD=$(rand_hex)

REDIS_PASSWORD=$(rand_hex)

NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=$(rand_hex)

ELASTIC_PASSWORD=$(rand_hex)

KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=$(rand_hex)

AI_ORCHESTRATOR_URL=http://ai_orchestrator:8020
MULTI_AGENTS_URL=http://multi_agents:8040
RAG_ENGINE_URL=http://rag_engine:8030

ANALYTICS_URL=http://backend:8000

INTERNAL_ONLY_MODE=true
ALLOW_EXTERNAL_APIS=false
STRICT_EGRESS_DENY=true
ENV

chmod 600 "$ENV_FILE"

echo
echo "Production environment created:"
echo "  $ENV_FILE"
echo
echo "Permissions:"
ls -l "$ENV_FILE"
EOF

chmod +x scripts/generate-production-env.sh

echo "[OK] Production secret generator created."

echo
echo "[7/10] Creating production Compose override..."

cat > infrastructure/docker/docker-compose.ai-fixes.yml <<'EOF'
services:

  ai_orchestrator:
    build:
      context: ../..
      dockerfile: services/ai_orchestrator/Dockerfile

    environment:
      MULTI_AGENTS_URL: http://multi_agents:8040

      INTERNAL_ONLY_MODE: "true"
      ALLOW_EXTERNAL_APIS: "false"

    expose:
      - "8020"

    depends_on:
      multi_agents:
        condition: service_started

    networks:
      - hsaai_private

    restart: unless-stopped

    healthcheck:
      test:
        - CMD-SHELL
        - python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8020/health', timeout=3)"
      interval: 20s
      timeout: 5s
      retries: 5
      start_period: 20s


  multi_agents:
    build:
      context: ../..
      dockerfile: services/multi_agents/Dockerfile

    environment:
      INTERNAL_ONLY_MODE: "true"
      ALLOW_EXTERNAL_APIS: "false"

      RAG_ENGINE_URL: http://rag_engine:8030
      LLM_GATEWAY_URL: http://llm_gateway:8090

    expose:
      - "8040"

    networks:
      - hsaai_private

    restart: unless-stopped


networks:
  hsaai_private:
    external: true
EOF

echo "[OK] AI Compose override created."

echo
echo "[8/10] Replacing deployment script with corrected version..."

cat > scripts/deploy-production.sh <<'EOF'
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
EOF

chmod +x scripts/deploy-production.sh

echo "[OK] Deployment script updated."

echo
echo "[9/10] Creating static validation script..."

cat > scripts/verify-hsaai.sh <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FAIL=0

check_file() {
    if [[ -f "$1" ]]; then
        echo "[OK] $1"
    else
        echo "[FAIL] missing: $1"
        FAIL=1
    fi
}

check_file services/backend_core/core/engine.py
check_file services/multi_agents/main.py
check_file services/multi_agents/Dockerfile
check_file services/ai_orchestrator/main.py
check_file services/ai_orchestrator/Dockerfile
check_file infrastructure/docker/docker-compose.production.yml
check_file infrastructure/docker/docker-compose.ai-fixes.yml
check_file scripts/deploy-production.sh

echo
echo "=== ORCHESTRATOR REFERENCES ==="

grep -RniE \
    'AI_ORCHESTRATOR_URL|ai_orchestrator|/orchestrate|multi_agents' \
    services infrastructure/docker scripts \
    --include='*.py' \
    --include='*.yml' \
    --include='*.yaml' \
    --include='*.sh' \
    2>/dev/null | head -200 || true

echo
echo "=== COMPOSE SERVICES ==="

grep -nE \
    '^[[:space:]]{2}[a-zA-Z0-9_-]+:' \
    infrastructure/docker/docker-compose.production.yml \
    2>/dev/null | head -100 || true

echo
echo "=== PYTHON COMPILE ==="

python -m compileall \
    services/backend_core \
    services/multi_agents \
    services/ai_orchestrator \
    packages/common \
    -q || FAIL=1

if [[ "$FAIL" -ne 0 ]]; then
    echo
    echo "VALIDATION FAILED"
    exit 1
fi

echo
echo "VALIDATION PASSED"
EOF

chmod +x scripts/verify-hsaai.sh

echo "[OK] Validation script created."

echo
echo "[10/10] Final static checks..."

python -m compileall \
    services/ai_orchestrator \
    services/multi_agents \
    services/backend_core \
    packages/common \
    -q

echo
echo "============================================================"
echo " HSAAI REPAIR FILES CREATED SUCCESSFULLY"
echo "============================================================"
echo
echo "Backup:"
echo "  $BACKUP_DIR"
echo
echo "Next:"
echo "  ./scripts/verify-hsaai.sh"
echo
echo "Then generate secrets:"
echo "  ./scripts/generate-production-env.sh"
echo
echo "Docker deployment:"
echo "  ./scripts/deploy-production.sh"
echo
