#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for tool in python node npm docker; do
 command -v "$tool" >/dev/null || { echo "BLOCKED: required tool $tool unavailable"; exit 2; }
done
python scripts/validate_release.py
python -m ruff check services packages --select F821,F822,F823,E9
python -m pytest tests --cov=services --cov=packages --cov-fail-under=80
(cd apps/web && npm ci && npm run lint && npm run type-check && npm test && npm audit --audit-level=high && NEXT_TELEMETRY_DISABLED=1 npm run build)
python -m pip_audit -r services/backend_core/requirements.txt
python scripts/validate_environment.py --env-file "${HSAAI_ENV_FILE:-deployment/generated/.env.production}"
docker compose --env-file "${HSAAI_ENV_FILE:-deployment/generated/.env.production}" -f docker-compose.production.yml config -q
docker compose --env-file "${HSAAI_ENV_FILE:-deployment/generated/.env.production}" -f docker-compose.production.yml build
echo 'Build gates passed. Complete SSO, database, RAG, load, security and restore acceptance on a test host.'
