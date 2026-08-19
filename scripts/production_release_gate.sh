#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[HSAAI] Production release gate started"

python -m compileall services >/tmp/hsaai_compile.log

echo "[OK] Python compile check passed"

if command -v pytest >/dev/null 2>&1; then
  pytest -q tests || { echo "[FAIL] tests failed"; exit 1; }
  echo "[OK] pytest passed"
else
  echo "[WARN] pytest is not installed; skipping test execution"
fi

# Secret scan scope:
# - Scan executable/config/source files that can actually carry committed secrets.
# - Exclude documentation/reports and this script to prevent false positives when
#   the forbidden pattern is mentioned as explanatory text.
# - Keep the forbidden pattern split into variables so this scanner does not
#   match itself.
secret_key_name="OPENAI_API_KEY"
secret_prefix="sk-"

secret_scan_hits="$({
  find . \
    -path './.git' -prune -o \
    -path './node_modules' -prune -o \
    -path './.next' -prune -o \
    -path './dist' -prune -o \
    -path './build' -prune -o \
    -type f \
    \( \
      -name '.env*' -o \
      -name '*.env' -o \
      -name '*.yml' -o \
      -name '*.yaml' -o \
      -name '*.json' -o \
      -name '*.py' -o \
      -name '*.ts' -o \
      -name '*.tsx' -o \
      -name '*.js' -o \
      -name '*.jsx' -o \
      -name '*.sh' -o \
      -name 'Dockerfile*' \
    \) \
    ! -path './scripts/production_release_gate.sh' \
    -print0 | xargs -0 grep -nE "${secret_key_name}[[:space:]]*=[[:space:]]*['\"]?${secret_prefix}" 2>/dev/null || true
} )"

if [ -n "$secret_scan_hits" ]; then
  echo "$secret_scan_hits"
  echo "[FAIL] Possible committed OpenAI secret found"
  exit 1
fi

echo "[OK] secret pattern check passed"

python scripts/validate_yaml_files.py
python scripts/verify_internal_only.py
echo "[OK] YAML and internal-only verification passed"

test -f docker-compose.production.yml || { echo "[FAIL] missing docker-compose.production.yml"; exit 1; }
test -f docs/operations/PRODUCTION_ACCEPTANCE_CHECKLIST.md || { echo "[FAIL] missing acceptance checklist"; exit 1; }
test -f docs/security/SECURITY_THREAT_MODEL.md || { echo "[FAIL] missing threat model"; exit 1; }

echo "[HSAAI] Production release gate completed"
