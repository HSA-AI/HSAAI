#!/usr/bin/env bash
# hsaai-env.sh (v3, portable) — Shared environment for all HSAAI native services
# Works from BOTH layouts (path autodetection — no hardcoded machine paths):
#   <project>/deployment/native/hsaai-env.sh   (packaged tree)
#   <parent>/scripts/hsaai-env.sh              (live sandbox, project at <parent>/hsaai)
# Override points (optional env vars BEFORE sourcing):
#   HSAAI_RUNTIME  — runtime dir (default: <project-parent>/runtime)
#   HSAAI_DATA_DIR — persistent data dir (default: $RUNTIME/data)
#   HSAAI_LOG_DIR  — logs dir       (default: $RUNTIME/logs)
set -uo pipefail

_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- locate project root (dir containing VERSION) ---
if [ -f "$_SELF_DIR/../../VERSION" ]; then
  HSAAI_ROOT="$(cd "$_SELF_DIR/../.." && pwd)"
elif [ -f "$_SELF_DIR/../hsaai/VERSION" ]; then
  HSAAI_ROOT="$(cd "$_SELF_DIR/../hsaai" && pwd)"
else
  HSAAI_ROOT="${HSAAI_HOME:-$(cd "$_SELF_DIR/../.." && pwd)}"
fi

export HSAAI_HOME="$HSAAI_ROOT"
export RUNTIME="${HSAAI_RUNTIME:-$(cd "$HSAAI_ROOT/.." && pwd)/runtime}"
export ROOTFS="$RUNTIME/rootfs"
export HSAOI_DATA="${HSAAI_DATA_DIR:-$RUNTIME/data}"
export HSAOI_LOGS="${HSAAI_LOG_DIR:-$RUNTIME/logs}"
export PGPORT="${PGPORT:-5432}"

export LD_LIBRARY_PATH="$ROOTFS/usr/lib/x86_64-linux-gnu:$ROOTFS/usr/lib:${LD_LIBRARY_PATH:-}"
export PATH="$ROOTFS/usr/lib/postgresql/17/bin:$ROOTFS/usr/bin:$PATH"

mkdir -p "$HSAOI_DATA" "$HSAOI_LOGS" 2>/dev/null || true
