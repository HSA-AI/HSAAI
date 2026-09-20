#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DIRS = [
    "apps/web/app", "apps/web/components", "services/api_gateway", "services/backend_core",
    "services/auth_service", "services/llm_gateway", "services/rag_engine",
    "services/multi_agents", "services/workflow_engine",
    "packages/common", "packages/governance",
    "infrastructure/docker", "infrastructure/kubernetes", "infrastructure/helm", "infrastructure/keycloak",
    "infrastructure/monitoring", "docs/architecture", "docs/operations", "docs/integration",
    "docs/governance", "docs/security", "docs/ui", "docs/api", "docs/deliverables",
    "tests/unit", "tests/integration", "tests/security", "tests/e2e", "tests/load", ".github/workflows"
]
REQUIRED_FILES = [
    "README.md", "LICENSE", "Makefile", ".gitignore", ".env.example", ".env.hsa-internal.example",
    ".env.production.example", "infrastructure/docker/docker-compose.hsa-internal.yml",
    "scripts/smoke_test.sh", "scripts/production_release_gate.sh"
]

def main():
    missing = []
    for d in REQUIRED_DIRS:
        if not (ROOT / d).is_dir():
            missing.append(d)
    for f in REQUIRED_FILES:
        if not (ROOT / f).is_file():
            missing.append(f)
    if missing:
        print("Missing required HSAAI paths:")
        for item in missing:
            print(f" - {item}")
        return 1
    print("HSAAI enterprise repository structure validation: OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())
