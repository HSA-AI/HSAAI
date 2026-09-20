#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${API_URL:?Set the internal API gateway base URL reachable from the acceptance host}"
: "${HSAAI_ACCEPTANCE_TOKEN:?Set a short-lived acceptance workspace token}"
export API_URL HSAAI_ACCEPTANCE_TOKEN
python scripts/acceptance_api.py
