#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# HSAAI Cross-Region PostgreSQL Logical Replication Applier (FIX I-13)
# ─────────────────────────────────────────────────────────────────────────────
#
# Purpose
#   `postgres-logical-replication.sql` references the replication password via
#   psql \set / :'REPLICATION_PASSWORD' interpolation. psql CANNOT read shell
#   env vars on its own — the value MUST be exported in this wrapper's
#   environment before psql is invoked, otherwise `echo "$REPLICATION_PASSWORD"`
#   inside the \set backtick expands to the empty string and the subscription
#   is created with a blank password (silent auth failure).
#
#   This script:
#     1. Refuses to run if REPLICATION_PASSWORD is unset or empty.
#     2. Refuses to run if PGHOST/PGUSER/PGDATABASE (or --connection flags) are unset.
#     3. Invokes psql with ON_ERROR_STOP=1 so a failed statement aborts the script.
#     4. Passes the SQL file's directory so relative psql \i includes still work.
#
# Usage
#   REPLICATION_PASSWORD='...' \
#     PGHOST=postgres.me-west-1.hsaai.internal \
#     PGUSER=hsaai_admin \
#     PGDATABASE=hsaai \
#     ./apply-replication.sh
#
#   Or, for a non-default target:
#   REPLICATION_PASSWORD='...' ./apply-replication.sh \
#     --host=postgres.me-west-1.hsaai.internal \
#     --user=hsaai_admin \
#     --dbname=hsaai
#
# Exit codes
#   0  — all statements applied
#   1  — missing env vars / invalid args
#   2  — psql binary not found
#   3  — psql reported an error
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SQL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_FILE="${SQL_DIR}/postgres-logical-replication.sql"

log()  { printf '[apply-replication] %s\n' "$*" >&2; }
fail() { log "ERROR: $*"; exit "${2:-1}"; }

# ─── 1. Validate env ────────────────────────────────────────────────────────
if [[ -z "${REPLICATION_PASSWORD:-}" ]]; then
  fail "REPLICATION_PASSWORD environment variable is required (set it before invoking this script). The SQL file uses \\\\set to read it; psql cannot discover it on its own."
fi

# ─── 2. Parse optional flags (override PG* env vars) ────────────────────────
PGHOST="${PGHOST:-}"
PGUSER="${PGUSER:-}"
PGDATABASE="${PGDATABASE:-}"
PGPORT="${PGPORT:-5432}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host=*)   PGHOST="${1#*=}"; shift ;;
    --user=*)   PGUSER="${1#*=}"; shift ;;
    --dbname=*) PGDATABASE="${1#*=}"; shift ;;
    --port=*)   PGPORT="${1#*=}"; shift ;;
    --file=*)   SQL_FILE="${1#*=}"; shift ;;
    -h|--help)
      sed -n '2,40p' "${BASH_SOURCE[0]}"
      exit 0
      ;;
    *) fail "Unknown argument: $1" ;;
  esac
done

[[ -n "$PGHOST"     ]] || fail "PGHOST (or --host=) is required."
[[ -n "$PGUSER"     ]] || fail "PGUSER (or --user=) is required."
[[ -n "$PGDATABASE" ]] || fail "PGDATABASE (or --dbname=) is required."
[[ -f "$SQL_FILE"   ]] || fail "SQL file not found: $SQL_FILE"

command -v psql >/dev/null 2>&1 || fail "psql not found in PATH" 2

# ─── 3. Export for psql \set backtick expansion ─────────────────────────────
export REPLICATION_PASSWORD PGHOST PGUSER PGDATABASE PGPORT

log "Target: ${PGUSER}@${PGHOST}:${PGPORT}/${PGDATABASE}"
log "SQL:    ${SQL_FILE}"

# ─── 4. Run psql ────────────────────────────────────────────────────────────
#   -v ON_ERROR_STOP=1  → abort on first error
#   -X                  → do not read ~/.psqlrc (deterministic behavior)
#   -f FILE             → execute the SQL file (psql \set / :'var' supported)
set +e
psql \
  -X \
  -v ON_ERROR_STOP=1 \
  --host="$PGHOST" \
  --port="$PGPORT" \
  --username="$PGUSER" \
  --dbname="$PGDATABASE" \
  -f "$SQL_FILE"
PSQL_EXIT=$?
set -e

if [[ $PSQL_EXIT -ne 0 ]]; then
  fail "psql exited with code ${PSQL_EXIT} — replication setup aborted." 3
fi

log "Replication SQL applied successfully."
exit 0
