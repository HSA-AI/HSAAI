#!/usr/bin/env bash
# generate-secrets.sh (v3) — Generate strong local secrets into <project>/.env.native
# The output file is machine-local: NEVER commit it to Git (.env.native must be in .gitignore).
# After rotation of HSAAI_DB_PASSWORD on an existing database, run:
#   psql -h 127.0.0.1 -U hsaai -d hsaai -c "ALTER USER hsaai PASSWORD '<new>';"
# Usage: generate-secrets.sh [--force]
set -euo pipefail

_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$_SELF_DIR/hsaai-env.sh"

OUT="$HSAAI_HOME/.env.native"

if [ -f "$OUT" ] && [ "${1:-}" != "--force" ]; then
  echo "ERROR: $OUT already exists (use --force to rotate)."
  exit 1
fi

gen() { python3 -c "import secrets; print(secrets.token_urlsafe($1))"; }

UMASK_OLD=$(umask); umask 077
cat > "$OUT" <<EOF
# HSAAI native deployment — machine-local secrets (generated $(date -u +%FT%TZ))
# SECURITY: never commit. Rotate quarterly. Distribute via your secrets manager in real production.

# --- Database ---
HSAAI_DB_PASSWORD=$(gen 24)

# --- OIDC client (matches KEYCLOAK_CLIENT_SECRET used by web/backend) ---
HSAAI_CLIENT_SECRET=$(gen 24)

# --- Desktop Gateway control plane ---
DESKTOP_API_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(16))")

# --- Application secrets ---
SECRET_KEY=$(gen 32)
JWT_SECRET=$(gen 32)

# --- Runtime environment ---
HSAAI_APP_ENV=production
EOF
umask "$UMASK_OLD"

chmod 600 "$OUT"
# Keep the gateway token file in sync so hsaai-ctl start gateway picks the same token
printf '%s' "$(grep '^DESKTOP_API_TOKEN=' "$OUT" | cut -d= -f2-)" > "$RUNTIME/desktop-gateway-token.txt"
chmod 600 "$RUNTIME/desktop-gateway-token.txt" 2>/dev/null || true

echo "OK: generated $OUT (permissions 600, values NOT printed)"
echo "Next steps:"
echo "  1) If the database already exists, rotate its password:"
echo "     psql -h 127.0.0.1 -U hsaai -d hsaai -c \"ALTER USER hsaai PASSWORD '<value from .env.native>';\""
echo "  2) restart services: hsaai-ctl restart all"
