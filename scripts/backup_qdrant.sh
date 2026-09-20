#!/usr/bin/env bash
set -euo pipefail
mkdir -p backups/qdrant
: "${QDRANT_URL:=http://qdrant:6333}"
COLLECTION="${1:-hsaai_documents}"
curl -fsS -X POST "$QDRANT_URL/collections/$COLLECTION/snapshots" | tee "backups/qdrant/${COLLECTION}_snapshot.json"
