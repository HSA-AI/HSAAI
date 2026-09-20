#!/usr/bin/env bash
# install-systemd-units.sh (v3) — Install hardened systemd units for the HSAAI native stack
# TARGET: real production hosts (VM/VPS) WITH systemd and root.
#   (Inside restricted sandboxes without systemd, keep using hsaai-ctl — this script is NOT for them.)
# Usage (root on the production host):
#   sudo bash deployment/production/install-systemd-units.sh [--user hsaai] [--home /opt/hsaai]
set -euo pipefail

INST_USER="hsaai"; HSAAI_HOME="/opt/hsaai"; RUNTIME="$(dirname "/opt/hsaai")/hsaai-runtime"
while [ $# -gt 0 ]; do case "$1" in
  --user) INST_USER="$2"; shift 2;;
  --home) HSAAI_HOME="$2"; RUNTIME="$(dirname "$2")/hsaai-runtime"; shift 2;;
  *) echo "unknown arg $1"; exit 2;;
esac; done
ROOTFS="$RUNTIME/rootfs"

[ "$(id -u)" = "0" ] || { echo "ERROR: run as root on the production host"; exit 1; }
[ -d "$HSAAI_HOME" ] || { echo "ERROR: project not found at $HSAAI_HOME"; exit 1; }

echo "== Installing HSAAI systemd units (user=$INST_USER, home=$HSAAI_HOME) =="

# --- environment file for all units ---
install -d -m 700 -o "$INST_USER" -g "$INST_USER" /etc/hsaai
if [ -f "$HSAAI_HOME/.env.native" ]; then
  install -m 600 -o "$INST_USER" -g "$INST_USER" "$HSAAI_HOME/.env.native" /etc/hsaai/hsaai.env
else
  echo "WARN: $HSAAI_HOME/.env.native missing — generating placeholder (fill values!)"
  install -m 600 -o "$INST_USER" -g "$INST_USER" /dev/null /etc/hsaai/hsaai.env
  grep -vE '^#|^$' "$HSAAI_HOME/deployment/native/env.native.example" | sed 's/<REPLACE_ME[^>]*>//' >> /etc/hsaai/hsaai.env || true
  # SECURITY FIX (audit P2-5): the installer used to proceed with EMPTY
  # secrets. Refuse to install production units until real values are set.
  echo "ERROR: refusing to install units with placeholder secrets."
  echo "       Fill /etc/hsaai/hsaai.env (POSTGRES_PASSWORD, KEYCLOAK_CLIENT_SECRET, DESKTOP_API_TOKEN)"
  echo "       — preferably create $HSAAI_HOME/.env.native from env.native.example first — then re-run."
  exit 1
fi

# Fail closed if the env file still contains unfilled placeholders.
if grep -qE '^(POSTGRES_PASSWORD|KEYCLOAK_CLIENT_SECRET|DESKTOP_API_TOKEN)=$' /etc/hsaai/hsaai.env 2>/dev/null \
   || ! grep -qE '^POSTGRES_PASSWORD=.+' /etc/hsaai/hsaai.env 2>/dev/null; then
  echo "ERROR: /etc/hsaai/hsaai.env has empty/placeholder secrets (POSTGRES_PASSWORD at minimum must be set)."
  exit 1
fi

HARDENING="# --- hardening ---
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes"

PGDATA="$RUNTIME/data/pgdata"
SOCKDIR="$RUNTIME/data/sockets"

unit() { # name, exec, extra-lines, readwrite-paths
  local name="$1" exec="$2" extra="${3:-}" rwp="${4:-}"
  cat > "/etc/systemd/system/$name.service" <<EOF
[Unit]
Description=HSAAI $name (native stack)
After=network.target
$( [ "$name" != "hsaai-postgres" ] && echo "After=hsaai-postgres.service" )
$( [ "$name" != "hsaai-postgres" ] && echo "Wants=hsaai-postgres.service" )

[Service]
User=$INST_USER
Group=$INST_USER
EnvironmentFile=/etc/hsaai/hsaai.env
Environment=HSAAI_RUNTIME=$RUNTIME
Environment=LD_LIBRARY_PATH=$ROOTFS/usr/lib/x86_64-linux-gnu
Environment=PATH=$ROOTFS/usr/lib/postgresql/17/bin:$ROOTFS/usr/bin:/usr/local/bin:/usr/bin:/bin
WorkingDirectory=$HSAAI_HOME
ExecStart=$exec
Restart=on-failure
RestartSec=3
TimeoutStartSec=90
$HARDENING
ReadWritePaths=$RUNTIME/data $RUNTIME/logs $ROOTFS $HSAAI_HOME $rwp
$extra

[Install]
WantedBy=multi-user.target
EOF
  echo "  installed: $name.service"
}

unit hsaai-postgres "postgres -D $PGDATA -p 5432 -c listen_addresses=127.0.0.1 -c unix_socket_directories=$SOCKDIR" "ExecStartPre=/usr/bin/mkdir -p $SOCKDIR"
unit hsaai-redis    "redis-server --port 6379 --bind 127.0.0.1 --dir $RUNTIME/data/redis --appendonly yes --appendfsync everysec"
unit hsaai-qdrant   "$RUNTIME/qdrant/qdrant" "Environment=QDRANT__SERVICE__HTTP_PORT=6333
Environment=QDRANT__SERVICE__GRPC_PORT=6334
Environment=QDRANT__STORAGE__STORAGE_PATH=$RUNTIME/data/qdrant_storage"
# SECURITY FIX (audit P1-2): the demo mock IdP is NO LONGER installed as a
# production unit by default — its admin credentials are committed to Git, so
# anyone with repo access could mint admin tokens. Real deployments must run
# Keycloak. Explicit opt-in (isolated demo VMs only) installs it.
if [ "${HSAAI_ENABLE_DEMO_IDP:-0}" = "1" ]; then
  echo "!! WARNING: installing the DEMO IdP as a systemd unit (HSAAI_ENABLE_DEMO_IDP=1)."
  echo "!! This is for isolated demo VMs only — production must use real Keycloak."
  unit hsaai-idp      "/usr/bin/node $HSAAI_HOME/deployment/native/mock-keycloak.js"
  DEMO_IDP_UNIT="hsaai-idp"
else
  echo "skip: hsaai-idp (demo IdP disabled — set HSAAI_ENABLE_DEMO_IDP=1 only for isolated demos)"
  DEMO_IDP_UNIT=""
fi
unit hsaai-backend  "$HSAAI_HOME/.venv-backend/bin/python -m uvicorn _demo_oidc_shim:app --host 127.0.0.1 --port 8000" "Environment=PYTHONPATH=$HSAAI_HOME:$HSAAI_HOME/services"
unit hsaai-web      "$HSAAI_HOME/apps/web/node_modules/.bin/next start -p 3000" "WorkingDirectory=$HSAAI_HOME/apps/web" "" "$HSAAI_HOME/apps/web/.next"
unit hsaai-gateway  "/usr/bin/python3 $HSAAI_HOME/deployment/native/desktop_gateway.py"

systemctl daemon-reload
echo "== done =="
echo "Next:"
# SECURITY FIX (audit P1-2): demo IdP unit only referenced when opted-in.
if [ -n "$DEMO_IDP_UNIT" ]; then
  echo "  systemctl enable --now hsaai-postgres hsaai-redis hsaai-qdrant hsaai-idp hsaai-backend hsaai-web hsaai-gateway"
else
  echo "  systemctl enable --now hsaai-postgres hsaai-redis hsaai-qdrant hsaai-backend hsaai-web hsaai-gateway"
fi
echo "  systemctl status hsaai-*   |   journalctl -u hsaai-backend -f"
echo "NOTE: desktop (Xvfb/x11vnc/noVNC) on production hosts should run inside a user session"
echo "      (loginctl enable-linger $INST_USER + hsaai-ctl start desktop) or a dedicated unit WITHOUT PrivateDevices."
