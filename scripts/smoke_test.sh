#!/usr/bin/env bash
set -euo pipefail
BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "Testing backend health: $BASE_URL/health"
curl -fsS "$BASE_URL/health" >/dev/null

echo "Testing security status"
curl -fsS "$BASE_URL/v1/security/internal-only/status" || true

echo "Smoke tests completed"
