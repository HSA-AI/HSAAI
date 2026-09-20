#!/usr/bin/env bash
# ============================================================================
# HSAAI Demo Runtime — Dockerless launcher (bash)
# ----------------------------------------------------------------------------
# Starts the three processes needed for the local demo environment:
#   1) mock-keycloak  (Demo IdP)               → http://127.0.0.1:9080
#   2) backend core + demo OIDC shim (FastAPI) → http://127.0.0.1:8080
#   3) Next.js web frontend                    → http://127.0.0.1:3000
#
# FIX (demo-runtime D-1/D-2/D-3): before these fixes the dockerless demo was
# broken — the documented scripts/mock-keycloak.js did not exist, /v1/chat had
# no bridge, and the Knowledge Hub / Smart Responses Next.js proxies 404'd.
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT/demo-runtime"
mkdir -p "$RUNTIME_DIR/logs"

export MOCK_KEYCLOAK_HOST=127.0.0.1
export MOCK_KEYCLOAK_PORT=9080
export KEYCLOAK_ISSUER="http://127.0.0.1:9080/realms/hsaai"
export KEYCLOAK_REALM=hsaai
export KEYCLOAK_CLIENT_ID=hsaai-frontend
export KEYCLOAK_CLIENT_SECRET=hsaai-demo-secret
export KEYCLOAK_AUDIENCE=hsaai-api
export DATABASE_URL="sqlite:///$RUNTIME_DIR/hsaai_demo.db"
export APP_ENV=development
export BACKEND_URL="http://127.0.0.1:8080"

echo "▶ [1/3] mock-keycloak (Demo IdP :9080)"
( cd "$ROOT" && node scripts/mock-keycloak.js > "$RUNTIME_DIR/logs/mock-keycloak.log" 2>&1 & echo $! > "$RUNTIME_DIR/mock-keycloak.pid" )

echo "▶ [2/3] backend core + demo OIDC shim (:8080)"
( cd "$ROOT/services" && PYTHONPATH="$ROOT:$ROOT/services:$ROOT/packages" \
    python3 -m uvicorn _demo_oidc_shim:app --host 127.0.0.1 --port 8080 \
    > "$RUNTIME_DIR/logs/backend.log" 2>&1 & echo $! > "$RUNTIME_DIR/backend.pid" )

echo "▶ [3/3] Next.js web (:3000)"
( cd "$ROOT/apps/web" && \
    NEXT_PUBLIC_API_URL="http://127.0.0.1:8080" \
    BACKEND_URL="http://127.0.0.1:8080" \
    KEYCLOAK_URL="http://127.0.0.1:9080" \
    KEYCLOAK_ISSUER="http://127.0.0.1:9080/realms/hsaai" \
    KEYCLOAK_REALM=hsaai \
    KEYCLOAK_CLIENT_ID=hsaai-frontend \
    KEYCLOAK_CLIENT_SECRET=hsaai-demo-secret \
    KEYCLOAK_AUDIENCE=hsaai-frontend \
    HSAAI_COOKIE_SECURE=false \
    npm run dev > "$RUNTIME_DIR/logs/web.log" 2>&1 & echo $! > "$RUNTIME_DIR/web.pid" )

echo ""
echo "⏳ waiting for services …"
for i in $(seq 1 60); do
  ok_idp=0; ok_api=0; ok_web=0
  curl -sf http://127.0.0.1:9080/health > /dev/null 2>&1 && ok_idp=1
  curl -sf http://127.0.0.1:8080/health > /dev/null 2>&1 && ok_api=1
  curl -sf -o /dev/null http://127.0.0.1:3000/login > /dev/null 2>&1 && ok_web=1
  [ "$ok_idp" = 1 ] && [ "$ok_api" = 1 ] && [ "$ok_web" = 1 ] && break
  sleep 2
done
echo ""
echo "✅ Demo IdP    : http://127.0.0.1:9080/health        ($([ $ok_idp = 1 ] && echo UP || echo DOWN))"
echo "✅ Backend API : http://127.0.0.1:8080/health        ($([ $ok_api = 1 ] && echo UP || echo DOWN))"
echo "✅ Web         : http://127.0.0.1:3000/login         ($([ $ok_web = 1 ] && echo UP || echo DOWN))"
echo ""
echo "Open http://127.0.0.1:3000 → تسجيل الدخول (Demo IdP يفتح جلسة مدير النظام)"
echo "Logs: $RUNTIME_DIR/logs/   |   Stop: bash demo-runtime/stop.sh"
