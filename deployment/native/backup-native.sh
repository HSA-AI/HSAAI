#!/usr/bin/env bash
# backup-native.sh (v3) — Consistent backup of the native HSAAI data layer
# Backs up: PostgreSQL (pg_dump, custom format) + Redis (RDB via BGSAVE) + Qdrant (snapshot API)
# Usage: backup-native.sh [output_dir]   (default: $RUNTIME/backups)
# NOTE: pg_dump is online-consistent (MVCC). Qdrant snapshot is online via API. Redis BGSAVE is non-blocking.
set -euo pipefail

_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$_SELF_DIR/hsaai-env.sh"

_envfile="$HSAAI_HOME/.env.native"; [ -f "$_envfile" ] && { set -a; . "$_envfile"; set +a; }
export PGPASSWORD="${HSAAI_DB_PASSWORD:-HsaaiLocal_2026}"

OUT="${1:-$RUNTIME/backups}"
TS=$(date +%Y%m%d-%H%M%S)
DEST="$OUT/$TS"
mkdir -p "$DEST"

echo "== HSAAI native backup → $DEST =="

# 1) PostgreSQL (logical, consistent)
echo "[1/3] postgres: pg_dump hsaai ..."
if pg_dump -h 127.0.0.1 -p 5432 -U hsaai -d hsaai -Fc -f "$DEST/postgres-hsaai.dump"; then
  ok_pg=$(ls -lh "$DEST/postgres-hsaai.dump" | awk '{print $5}')
  echo "      OK ($ok_pg)"
else
  echo "      FAIL: pg_dump failed"; exit 1
fi

# 2) Redis (BGSAVE → copy dump.rdb)
echo "[2/3] redis: BGSAVE + copy ..."
if redis-cli -h 127.0.0.1 -p 6379 bgsave >/dev/null 2>&1; then
  # wait for save completion
  for i in $(seq 1 30); do
    [ "$(redis-cli -h 127.0.0.1 -p 6379 lastsave 2>/dev/null)" = "$(redis-cli -h 127.0.0.1 -p 6379 lastsave 2>/dev/null)" ] && \
    [ "$(redis-cli -h 127.0.0.1 -p 6379 info persistence 2>/dev/null | grep -c rdb_bgsave_in_progress:1)" = "0" ] && break
    sleep 1
  done
  cp "$HSAOI_DATA/redis/dump.rdb" "$DEST/redis-dump.rdb" 2>/dev/null && echo "      OK" || { echo "      FAIL: dump.rdb not found"; exit 1; }
else
  echo "      FAIL: redis not reachable"; exit 1
fi

# 3) Qdrant (snapshot API → download)
echo "[3/3] qdrant: create + download snapshot ..."
SNAP=$(curl -sf -X POST "http://127.0.0.1:6333/collections/hsaai_knowledge/snapshots" | python3 -c "import sys,json;print(json.load(sys.stdin)['result']['name'])" 2>/dev/null || true)
if [ -n "${SNAP:-}" ]; then
  curl -sf "http://127.0.0.1:6333/collections/hsaai_knowledge/snapshots/$SNAP" -o "$DEST/qdrant-hsaai_knowledge.snapshot" \
    && echo "      OK ($SNAP)" || { echo "      FAIL: snapshot download"; exit 1; }
  # best-effort cleanup of remote snapshot
  curl -sf -X DELETE "http://127.0.0.1:6333/collections/hsaai_knowledge/snapshots/$SNAP" >/dev/null 2>&1 || true
else
  echo "      WARN: qdrant snapshot API unavailable — skipping (vector data NOT in this backup)"
fi

cat > "$DEST/MANIFEST.txt" <<EOF
HSAAI native backup manifest
created_utc: $(date -u +%FT%TZ)
postgres: postgres-hsaai.dump (custom format - restore via pg_restore)
redis:    redis-dump.rdb
qdrant:   qdrant-hsaai_knowledge.snapshot
host_user: $(id -un)
hsaai_version: $(cat "$HSAAI_HOME/VERSION" 2>/dev/null || echo unknown)
EOF

SIZE=$(du -sh "$DEST" | cut -f1)
echo "== backup complete: $DEST ($SIZE) =="
# retention: keep last 14
ls -1dt "$OUT"/20* 2>/dev/null | tail -n +15 | xargs -r rm -rf
echo "retention: kept last 14 backups under $OUT"
