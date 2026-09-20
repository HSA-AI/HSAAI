#!/usr/bin/env bash
# setup-runtime.sh (v3, portable) — Download official Debian debs and extract into user-space rootfs
# No root required: dpkg -x extracts into user dirs. Does NOT bypass any kernel/security restriction.
# Layout: works from <project>/deployment/native/ (packaged) or <parent>/scripts/ (live sandbox).
set -euo pipefail

_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$_SELF_DIR/hsaai-env.sh"

ROOTFS="$RUNTIME/rootfs"
DEBS="$RUNTIME/debs"
URLS="${HSAAI_DEB_URLS:-$RUNTIME/deb_urls.txt}"

mkdir -p "$ROOTFS" "$DEBS"

if [ ! -s "$URLS" ]; then
  echo "ERROR: $URLS not found."
  echo "Generate it on a matching Debian 13 machine with the same sources:"
  echo "  apt-get install --print-uris --yes <packages> | grep -oP \"^'[^']+'\" | tr -d \"'\" > deb_urls.txt"
  echo "Then place it at \$HSAAI_DEB_URLS or $URLS"
  exit 1
fi

echo "[1/3] Downloading $(wc -l < "$URLS") packages..."
cd "$DEBS"
n=0
while IFS= read -r url; do
  f=$(basename "$url" | sed 's/%2b/+/g; s/%7e/~/g; s/%2B/+/g')
  if [ ! -f "$f" ]; then
    curl -fsSL --retry 3 -o "$f" "$url" || { echo "FAIL: $url"; exit 1; }
  fi
  n=$((n+1))
done < "$URLS"
echo "Downloaded $n debs."

echo "[2/3] Extracting into rootfs..."
for d in "$DEBS"/*.deb; do
  dpkg -x "$d" "$ROOTFS"
done
echo "Extracted $(ls "$DEBS"/*.deb | wc -l | tr -d ' ') debs."

echo "[3/3] Done. Rootfs layout:"
ls "$ROOTFS"
