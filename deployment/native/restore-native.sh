#!/usr/bin/env bash
# restore-native.sh (v3) — Restore HSAAI native data layer from a backup dir created by backup-native.sh
# Usage: restore-native.sh <backup_dir> [--drop]
#   --drop : drop and recreate the hsaai database first (needed when restoring into a live cluster)
# Components: postgres (pg_restore) + redis (stop → replace RDB → start) + qdrant (recover snapshot)
set -euo pipefail

_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$_SELF_DIR/hsaai-env.sh"

BACKUP="${1:-}"
[ -z "$BACKUP" ] && { echo "usage: restore-native.sh <backup_dir> [--drop]"; exit 2; }
[ -d "$BACKUP" ] || { echo "ERROR: backup dir not found: $BACKUP"; exit 2; }
DROP="${2:-}"

_envfile="$HSAAI_HOME/.env.native"; [ -f "$_envfile" ] && { set -a; . "$_envfile"; set +a; }
export PGPASSWORD="${HSAAI_DB_PASSWORD:-HsaaiLocal_2026}"

echo "== HSAAI native restore from $BACKUP =="

# 1) PostgreSQL
if [ -f "$BACKUP/postgres-hsaai.dump" ]; then
  echo "[1/3] postgres: pg_restore ..."
  if [ "$DROP" = "--drop" ]; then
    psql -h 127.0.0.1 -p 5432 -U hsaai -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='hsaai' AND pid<>pg_backend_pid();" >/dev/null
    psql -h 127.0.0.1 -p 5432 -U hsaai -d postgres -c "DROP DATABASE IF EXISTS hsaai;" >/dev/null
    psql -h 127.0.0.1 -p 5432 -U hsaai -d postgres -c "CREATE DATABASE hsaai OWNER hsaai;" >/dev/null
  fi
  pg_restore -h 127.0.0.1 -p 5432 -U hsaai -d hsaai --no-owner --role=hsaai "$BACKUP/postgres-hsaai.dump" \
    && echo "      OK" || { echo "      FAIL: pg_restore"; exit 1; }
else
  echo "[1/3] postgres: dump missing — skipped"
fi

# 2) Redis (requires restart)
if [ -f "$BACKUP/redis-dump.rdb" ]; then
  echo "[2/3] redis: stop → replace RDB → start ..."
  redis-cli -h 127.0.0.1 -p 6379 shutdown nosave 2>/dev/null || true
  sleep 1
  cp "$BACKUP/redis-dump.rdb" "$HSAOI_DATA/redis/dump.rdb"
  redis-server --port 6379 --bind 127.0.0.1 --dir "$HSAOI_DATA/redis" --daemonize yes \
    --pidfile "$HSAOI_DATA/redis/redis.pid" --logfile "$HSAOI_LOGS/redis.log" \
    --appendonly yes --appendfsync everysec
  for i in $(seq 1 15); do redis-cli -h 127.0.0.1 -p 6379 ping 2>/dev/null | grep -q PONG && break; sleep 1; done
  redis-cli -h 127.0.0.1 -p 6379 ping | grep -q PONG && echo "      OK" || { echo "      FAIL: redis did not come back"; exit 1; }
else
  echo "[2/3] redis: dump missing — skipped"
fi

# 3) Qdrant (recover snapshot via API)
if [ -f "$BACKUP"/qdrant-hsaai_knowledge.snapshot ]; then
  echo "[3/3] qdrant: upload + recover snapshot ..."
  SNAP_NAME="restore-$(date +%Y%m%d%H%M%S).snapshot"
  cp "$BACKUP"/qdrant-hsaai_knowledge.snapshot "$HSAOI_DATA/qdrant_storage/snapshots/$SNAP_NAME" 2>/dev/null || {
    mkdir -p "$HSAOI_DATA/qdrant_storage/snapshots"; cp "$BACKUP"/qdrant-hsaai_knowledge.snapshot "$HSAOI_DATA/qdrant_storage/snapshots/$SNAP_NAME"; }
  curl -sf -X PUT "http://127.0.0.1:6333/collections/hsaai_knowledge/snapshots/upload" \
    >/dev/null 2>&1 || true
  curl -sf -X POST "http://127.0.0.1:6333/collections/hsaai_knowledge/snapshots/$SNAP_NAME/recover" -H 'Content-Type: application/json' -d '{}' \
    >/dev/null && echo "      OK" || echo "      WARN: API recover failed — verify manually via qdrant dashboard"
else
  echo "[3/3] qdrant: snapshot missing — skipped"
fi

echo "== restore complete — verify with: hsaai-ctl status && curl -s http://127.0.0.1:8000/ready =="
