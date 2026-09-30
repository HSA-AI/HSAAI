#!/usr/bin/env python3

"""Final source/package integrity checks for HSAAI release candidates."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []

REQUIRED_FILES = [
    ".github/workflows/enterprise-e2e.yml",
    ".github/workflows/enterprise-runtime-acceptance.yml",
    ".github/workflows/kubernetes-acceptance.yml",
    ".github/workflows/kubernetes-runtime-acceptance.yml",
    ".github/workflows/production-coverage.yml",
    ".github/workflows/production-dependency-audit.yml",
    ".github/workflows/production-enterprise-wiring.yml",
    ".github/workflows/production-images.yml",
    ".github/workflows/production-runtime-parity.yml",
    ".github/workflows/security-scan.yml",
    "scripts/deploy-production.sh",
    "scripts/package_delivery.py",
    "scripts/production_release_gate.sh",
    "scripts/production_runtime_parity.sh",
    "scripts/validate_release.py",
    "docker-compose.production.yml",
]


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if result.returncode != 0:
        ERRORS.append(
            f"git {' '.join(args)} failed: {result.stderr.strip()}"
        )
        return ""

    return result.stdout


for relative in REQUIRED_FILES:
    if not (ROOT / relative).is_file():
        ERRORS.append(f"Required release file missing: {relative}")


tracked = {
    line.strip()
    for line in git("ls-files").splitlines()
    if line.strip()
}

for name in sorted(tracked):
    path = Path(name)
    base = path.name
    lower = base.lower()

    if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
        ERRORS.append(f"Generated Python artifact is tracked: {name}")

    if (
        base.startswith(".env")
        and "example" not in lower
        and "sample" not in lower
        and "template" not in lower
    ):
        ERRORS.append(f"Private environment file is tracked: {name}")

    if base in {"id_rsa", "id_ed25519"}:
        ERRORS.append(f"Private key candidate is tracked: {name}")

    if path.suffix.lower() in {".key", ".p12", ".pfx"}:
        ERRORS.append(f"Private credential candidate is tracked: {name}")


package_script = ROOT / "scripts/package_delivery.py"

if package_script.is_file():
    spec = importlib.util.spec_from_file_location(
        "hsaai_package_delivery",
        package_script,
    )

    if spec is None or spec.loader is None:
        ERRORS.append("Unable to inspect package_delivery.py")
    else:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        exclusions = set(getattr(module, "EXCLUDE_PARTS", set()))

        required_exclusions = {
            ".git",
            "node_modules",
            ".next",
            ".venv",
            "venv",
            "__pycache__",
            ".pytest_cache",
        }

        missing = sorted(required_exclusions - exclusions)

        if missing:
            ERRORS.append(
                "Packaging exclusions missing: " + ", ".join(missing)
            )

        excluded_name = getattr(module, "excluded_name", None)

        if excluded_name is None:
            ERRORS.append(
                "Packaging policy does not expose excluded_name()"
            )
        else:
            if not excluded_name(".env"):
                ERRORS.append(
                    "Packaging policy does not exclude private .env files"
                )

            if not excluded_name(".env.production"):
                ERRORS.append(
                    "Packaging policy does not exclude production .env files"
                )

            if excluded_name(".env.example"):
                ERRORS.append(
                    "Packaging policy incorrectly excludes safe .env example files"
                )

            if not excluded_name("tmp/hsaai_test.db"):
                ERRORS.append(
                    "Packaging policy does not exclude runtime databases"
                )


status = git("status", "--porcelain")

if status.strip():
    ERRORS.append(
        "Working tree is not clean during final release integrity validation"
    )


report = {
    "status": "failed" if ERRORS else "passed",
    "scope": "final-release-source-integrity",
    "required_files": len(REQUIRED_FILES),
    "tracked_files": len(tracked),
    "errors": ERRORS,
    "external_kubernetes_runtime": "separate operator acceptance required",
}

print(json.dumps(report, indent=2))

sys.exit(1 if ERRORS else 0)
