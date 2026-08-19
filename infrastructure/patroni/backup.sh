#!/bin/bash
# HSAAI PostgreSQL HA Backup Script (v4.0)
#
# FIX I-10: Connect directly to HAProxy write port (5430) — NOT PgBouncer.
# PgBouncer transaction-mode pooling is incompatible with pg_dump/pg_dumpall
# (they require session state and multi-statement transactions). Was producing
# silently corrupted or partial backups.

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"

# FIX I-10: Connect to HAProxy write port (5430), NOT PgBouncer (6432).
# HAProxy routes writes to the Patroni leader; PgBouncer transaction pooling
# breaks pg_dump/pg_dumpall's session requirements.
PGHOST="${PGHOST:-haproxy}"
PGPORT="${PGPORT:-5430}"
PGUSER="${PGUSER:-hsaai}"

DATABASES=("hsaai" "keycloak")

mkdir -p "$BACKUP_DIR"

DATE=$(date -u +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/hsaai_${DATE}.sql.gz"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting PostgreSQL backup → $BACKUP_FILE (via $PGHOST:$PGPORT)"

# Dump each database in custom format (parallel-restore friendly)
for db in "${DATABASES[@]}"; do
    echo "  → Dumping database: $db"
    PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
        --host="$PGHOST" \
        --port="$PGPORT" \
        --username="$PGUSER" \
        --dbname="$db" \
        --format=custom \
        --compress=9 \
        --no-owner \
        --no-privileges \
        --file="$BACKUP_DIR/${db}_${DATE}.dump"
done

# Also create a combined SQL dump (gzip compressed) — for role + schema migration
PGPASSWORD="$POSTGRES_PASSWORD" pg_dumpall \
    --host="$PGHOST" \
    --port="$PGPORT" \
    --username="$PGUSER" \
    --no-role-passwords \
    | gzip -9 > "$BACKUP_FILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Backup complete: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"

# Prune old backups
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Pruning backups older than ${RETENTION_DAYS} days..."
find "$BACKUP_DIR" -name "hsaai_*.sql.gz" -mtime +"$RETENTION_DAYS" -delete
find "$BACKUP_DIR" -name "*_*.dump" -mtime +"$RETENTION_DAYS" -delete

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Backup finished."
