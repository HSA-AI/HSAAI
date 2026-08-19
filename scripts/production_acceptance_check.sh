#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.dev.yml}"
API_URL="${API_URL:-http://localhost:8080}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
MODEL="${LOCAL_LLM_MODEL:-llama3.1:8b-instruct}"
TMP_DIR="${TMP_DIR:-/tmp/hsaai_acceptance}"
mkdir -p "$TMP_DIR"

need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: missing command: $1"; exit 2; }; }
need curl
need docker

printf '\n[1/9] Validate Docker Compose config...\n'
docker compose -f "$COMPOSE_FILE" config >/dev/null

printf '\n[2/9] Start HSAAI stack...\n'
docker compose -f "$COMPOSE_FILE" up -d --build

printf '\n[3/9] Wait for public endpoints...\n'
for i in {1..90}; do
  if curl -fsS "$API_URL/health" >/dev/null && curl -fsS "$FRONTEND_URL" >/dev/null; then break; fi
  sleep 2
  if [ "$i" -eq 90 ]; then echo "ERROR: API/frontend did not become healthy"; exit 1; fi
done

printf '\n[4/9] Check service health endpoints...\n'
for endpoint in \
  "$API_URL/health" \
  "http://localhost:8000/health" \
  "http://localhost:8010/health" \
  "http://localhost:8020/health" \
  "http://localhost:8030/health" \
  "http://localhost:8090/health"; do
  echo "- $endpoint"
  curl -fsS "$endpoint" | tee "$TMP_DIR/$(echo "$endpoint" | sed 's#[/:]#_#g').json" >/dev/null
done

printf '\n[5/9] Verify Ollama model availability...\n'
if ! curl -fsS "$OLLAMA_URL/api/tags" | grep -q "${MODEL%%:*}"; then
  echo "Model $MODEL is not installed. Pulling it now..."
  docker compose -f "$COMPOSE_FILE" exec -T local_llm ollama pull "$MODEL"
fi

printf '\n[6/9] Test /v1/chat through API Gateway...\n'
curl -fsS -X POST "$API_URL/v1/chat" \
  -H 'Content-Type: application/json' \
  -H 'X-Tenant-ID: default' \
  -H 'X-Workspace-ID: default' \
  -d '{"user":"acceptance","message":"اكتب رداً قصيراً يؤكد أن HSAAI يعمل","workspace_id":"default"}' \
  | tee "$TMP_DIR/chat.json" >/dev/null

printf '\n[7/9] Upload sample document to RAG and verify Qdrant search...\n'
cat > "$TMP_DIR/sample_hsaai_policy.txt" <<'TXT'
HSAAI Acceptance Sample
This document confirms that HSAAI RAG indexing is working.
Policy marker: HSA-RAG-ACCEPTANCE-2026.
TXT
curl -fsS -X POST "$API_URL/v1/rag/documents/upload" \
  -F "tenant_id=default" \
  -F "workspace_id=default" \
  -F "file=@$TMP_DIR/sample_hsaai_policy.txt;type=text/plain" \
  | tee "$TMP_DIR/rag_upload.json" >/dev/null
curl -fsS -X POST "$API_URL/v1/rag/search" \
  -H 'Content-Type: application/json' \
  -d '{"query":"HSA-RAG-ACCEPTANCE-2026","tenant_id":"default","workspace_id":"default","top_k":5,"mode":"hybrid"}' \
  | tee "$TMP_DIR/rag_search.json" >/dev/null
grep -q "HSA-RAG-ACCEPTANCE-2026" "$TMP_DIR/rag_search.json"

printf '\n[8/9] Verify internal-only security status...\n'
curl -fsS "$API_URL/v1/security/internal-only/status" | tee "$TMP_DIR/security.json" >/dev/null || true

printf '\n[9/9] Acceptance result...\n'
echo "PASS: HSAAI compose, chat, local LLM gateway, RAG upload/search and health checks completed. Evidence stored in $TMP_DIR"
