#!/usr/bin/env bash
set -euo pipefail
: "${RESTORE_DATABASE:?Set a NEW disposable database named hsaai_restore_*}"
: "${PGHOST:?Set an isolated PostgreSQL host}"
: "${PGUSER:?Set the restore operator}"
case "$RESTORE_DATABASE" in hsaai_restore_*) ;; *) echo 'Refusing non-drill database'; exit 2;; esac
backup="${1:?Pass a .sql.gz backup}"
gzip -t "$backup"
createdb "$RESTORE_DATABASE"
gzip -cd "$backup" | psql --set ON_ERROR_STOP=1 --dbname "$RESTORE_DATABASE"
psql --set ON_ERROR_STOP=1 --dbname "$RESTORE_DATABASE" --command 'SELECT version_num FROM alembic_version;'
echo 'Restore completed in disposable DB; compare row counts and run acceptance before signing.'
