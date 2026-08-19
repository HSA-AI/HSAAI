#!/usr/bin/env bash
set -euo pipefail
mkdir -p backups/postgres
TS=$(date +%Y%m%d_%H%M%S)
: "${POSTGRES_HOST:=postgres}"
: "${POSTGRES_USER:=hsaai}"
: "${POSTGRES_DB:=hsaai}"
pg_dump -h "$POSTGRES_HOST" -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "backups/postgres/hsaai_${TS}.sql.gz"
echo "Backup written to backups/postgres/hsaai_${TS}.sql.gz"
