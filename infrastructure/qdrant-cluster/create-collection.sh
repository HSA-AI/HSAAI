#!/bin/bash
# HSAAI Qdrant Collection Creation Script (v3.0)
# Creates the hsaai_knowledge collection with sharding + replication.

set -euo pipefail

QDRANT_URL="${QDRANT_URL:-http://nginx-qdrant:6333}"
COLLECTION="${COLLECTION:-hsaai_knowledge}"
VECTOR_SIZE="${VECTOR_SIZE:-384}"
DISTANCE="${DISTANCE:-Cosine}"
SHARD_NUMBER="${SHARD_NUMBER:-4}"
REPLICATION_FACTOR="${REPLICATION_FACTOR:-2}"
WRITE_CONSISTENCY="${WRITE_CONSISTENCY:-2}"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Creating Qdrant collection: $COLLECTION"
echo "  Vector size: $VECTOR_SIZE"
echo "  Distance: $DISTANCE"
echo "  Shard number: $SHARD_NUMBER"
echo "  Replication factor: $REPLICATION_FACTOR"
echo "  Write consistency factor: $WRITE_CONSISTENCY"
echo ""

# Create collection with sharding + replication
RESPONSE=$(curl -sS -X PUT "$QDRANT_URL/collections/$COLLECTION" \
  -H "Content-Type: application/json" \
  -d "{
    \"vectors\": {\"size\": $VECTOR_SIZE, \"distance\": \"$DISTANCE\"},
    \"shard_number\": $SHARD_NUMBER,
    \"replication_factor\": $REPLICATION_FACTOR,
    \"write_consistency_factor\": $WRITE_CONSISTENCY,
    \"read_consistency_factor\": 1,
    \"on_disk_payload\": true,
    \"optimizers_config\": {
      \"default_segment_number\": 4,
      \"indexing_threshold\": 20000,
      \"flush_interval_sec\": 5
    }
  }")

echo "Response: $RESPONSE"

# Verify collection
echo ""
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Verifying collection..."
curl -sS "$QDRANT_URL/collections/$COLLECTION" | python3 -m json.tool || true

echo ""
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Collection creation complete."
