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
