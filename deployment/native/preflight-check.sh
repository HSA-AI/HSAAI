#!/usr/bin/env bash
# preflight-check.sh (v3) — Production preflight validation BEFORE starting HSAAI native stack
# Checks: rootfs binaries, runtimes (python venv / node_modules), ports, disk, data dirs, token.
# Usage: preflight-check.sh [--quick]   (exit 0 = ready, 1 = critical failures, 2 = warnings only)
set -uo pipefail

_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$_SELF_DIR/hsaai-env.sh"

FAIL=0; WARN=0
ok()   { printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; FAIL=$((FAIL+1)); }
warn() { printf '  \033[33mWARN\033[0m  %s\n' "$1"; WARN=$((WARN+1)); }

echo "== HSAAI preflight (project: $HSAAI_HOME) =="

echo "[1/6] rootfs binaries"
for b in postgres redis-server qdrant Xvfb x11vnc websockify openbox xterm ffmpeg xdotool; do
  found=""
  [ -x "$ROOTFS/usr/bin/$b" ] && found="$ROOTFS/usr/bin/$b"
  [ -x "$ROOTFS/usr/lib/postgresql/17/bin/$b" ] && found="$ROOTFS/usr/lib/postgresql/17/bin/$b"
  # component-specific locations
  [ "$b" = "qdrant" ] && [ -x "$RUNTIME/qdrant/qdrant" ] && found="$RUNTIME/qdrant/qdrant"
  [ "$b" = "websockify" ] && [ -x "$RUNTIME/venv-desktop/bin/websockify" ] && found="$RUNTIME/venv-desktop/bin/websockify"
  [ -z "$found" ] && command -v "$b" >/dev/null 2>&1 && found="(system PATH)"
  [ -n "$found" ] && ok "$b → $found" || bad "$b missing (run setup-runtime.sh)"
done

echo "[2/6] qdrant binary location"
if [ -x "$RUNTIME/qdrant/qdrant" ]; then ok "$RUNTIME/qdrant/qdrant"
else bad "qdrant binary not at $RUNTIME/qdrant/qdrant"; fi

echo "[3/6] application runtimes"
[ -x "$HSAAI_HOME/.venv-backend/bin/python" ] && ok ".venv-backend python" || bad "backend venv missing (create + pip install -r services/backend_core/requirements.txt)"
[ -d "$HSAAI_HOME/apps/web/node_modules" ] && ok "web node_modules" || bad "web deps missing (npm install in apps/web)"
[ -d "$HSAAI_HOME/apps/web/.next" ] && ok "web production build (.next)" || warn "no .next build — run: cd apps/web && npm run build"
command -v node >/dev/null 2>&1 && ok "node runtime for mock IdP ($(node --version)) — uses builtins only" || bad "node missing (mock IdP requirement)"

echo "[4/6] ports free (5432 6379 6333 8000 3000 6080 8600 9080)"
for p in 5432 6379 6333 8000 3000 6080 8600 9080; do
  if command -v ss >/dev/null 2>&1; then
    if ss -tln 2>/dev/null | grep -q ":$p "; then
      # already listening might mean HSAAI already running — only warn
      warn "port $p already in use (if HSAAI is running, this is expected)"
    else ok "port $p free"; fi
  else warn "ss not available — cannot check ports"; break
  fi
done

echo "[5/6] storage"
avail_kb=$(df -Pk "$HSAOI_DATA" | awk 'NR==2{print $4}')
if [ "${avail_kb:-0}" -gt 2097152 ]; then ok "data volume has $((avail_kb/1024/1024))GB free (need >2GB)"
else bad "data volume low: $((avail_kb/1024))MB free (need >2GB)"; fi
for d in "$HSAOI_DATA" "$HSAOI_LOGS"; do
  [ -w "$d" ] && ok "writable: $d" || bad "not writable: $d"
done

echo "[6/6] security"
tok="$RUNTIME/desktop-gateway-token.txt"
if [ -s "$tok" ]; then
  ok "gateway token file present"
  perm=$(stat -c '%a' "$tok" 2>/dev/null || echo '?')
  [ "$perm" = "600" ] && ok "token file permissions 600" || warn "token file perms $perm (recommend 600)"
else warn "gateway token missing — will be auto-generated on first 'hsaai-ctl start gateway'"
fi
if [ -f "$HSAAI_HOME/.env.native" ]; then
  ok ".env.native present (secrets externalized)"
  [ "$(stat -c '%a' "$HSAAI_HOME/.env.native")" = "600" ] && ok ".env.native permissions 600" || warn ".env.native should be chmod 600"
else
  [ "${1:-}" = "--quick" ] && warn ".env.native not found (dev default passwords in use)" \
    || warn ".env.native not found — run generate-secrets.sh before production"
fi
grep -q '^\.env\.native$' "$HSAAI_HOME/.gitignore" 2>/dev/null && ok ".env.native git-ignored" || warn "add '.env.native' to .gitignore"

echo "== result =="
if [ "$FAIL" -gt 0 ]; then echo "CRITICAL FAILURES: $FAIL (fix before start)"; exit 1
elif [ "$WARN" -gt 0 ]; then echo "READY with warnings: $WARN"; exit 2
else echo "READY — all checks passed"; exit 0
fi
