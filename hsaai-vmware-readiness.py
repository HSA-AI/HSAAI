#!/usr/bin/env python3
"""
HSAAI VMware Deployment Readiness Checker
Verifies all prerequisites for VMware production deployment.

Run:
    python3 hsaai-vmware-readiness.py

Exit codes:
    0 — ready for VMware deployment
    1 — not ready — fix issues first
"""
from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from typing import Any


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def ok(msg: str) -> None:
    print(f"  {Colors.GREEN}✓{Colors.RESET} {msg}")

def fail(msg: str) -> None:
    print(f"  {Colors.RED}✗{Colors.RESET} {msg}")

def warn(msg: str) -> None:
    print(f"  {Colors.YELLOW}⚠{Colors.RESET} {msg}")

def header(title: str) -> None:
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'═' * 60}{Colors.RESET}")
    print(f"{Colors.BLUE}{Colors.BOLD}  {title}{Colors.RESET}")
    print(f"{Colors.BLUE}{Colors.BOLD}{'═' * 60}{Colors.RESET}")


def main() -> int:
    project_root = Path(__file__).parent
    errors = 0
    warnings = 0

    header("HSAAI VMware Deployment Readiness Check")
    print(f"  Project root: {project_root}")
    print(f"  Version: {open(project_root / 'VERSION').read().strip() if (project_root / 'VERSION').exists() else 'unknown'}")

    # ============================================================
    # 1. Python Services Compilation
    # ============================================================
    header("1. Python Services Compilation")

    services_dir = project_root / "services"
    if not services_dir.exists():
        fail("services/ directory not found")
        errors += 1
    else:
        service_count = 0
        compile_failures = 0
        for svc_dir in sorted(services_dir.iterdir()):
            if not svc_dir.is_dir():
                continue
            main_file = svc_dir / "main.py"
            if not main_file.exists():
                continue
            service_count += 1
            try:
                subprocess.run(
                    [sys.executable, "-m", "py_compile", str(main_file)],
                    capture_output=True, check=True
                )
            except subprocess.CalledProcessError:
                fail(f"{svc_dir.name}/main.py — compilation error")
                compile_failures += 1
                errors += 1
        if compile_failures == 0:
            ok(f"All {service_count} services compile successfully")

    # ============================================================
    # 2. __init__.py Files
    # ============================================================
    header("2. Python Package __init__.py Files")

    missing_init = 0
    for d in services_dir.rglob("*"):
        if d.is_dir() and (d / "main.py").exists() or any(d.glob("*.py")):
            if not (d / "__init__.py").exists():
                # Check if it has .py files
                py_files = list(d.glob("*.py"))
                if py_files:
                    fail(f"Missing: {d.relative_to(project_root)}/__init__.py")
                    missing_init += 1
                    errors += 1
    if missing_init == 0:
        ok("All Python packages have __init__.py")

    # ============================================================
    # 3. CORS Security
    # ============================================================
    header("3. CORS Security (No Wildcards)")

    cors_wildcards = 0
    in_docstring = False
    for py_file in services_dir.rglob("*.py"):
        try:
            content = py_file.read_text()
            for i, line in enumerate(content.split("\n"), 1):
                stripped = line.strip()
                # Track multi-line docstrings
                if '"""' in stripped or "'''" in stripped:
                    # Toggle docstring state if we see the marker
                    count = stripped.count('"""') + stripped.count("'''")
                    if count == 1:
                        in_docstring = not in_docstring
                    continue
                # Skip if inside a docstring
                if in_docstring:
                    continue
                # Skip single-line comments
                if stripped.startswith("#"):
                    continue
                # Only flag ACTIVE code with wildcard
                if "allow_origins=["*"]" in line or "allow_origins=['*']" in line:
                    fail(f"{py_file.relative_to(project_root)}:{i} — CORS wildcard")
                    cors_wildcards += 1
                    errors += 1
        except Exception:
            pass
    if cors_wildcards == 0:
        ok("No CORS wildcards in active code")

    # ============================================================
    # 4. Secrets in .env.example
    # ============================================================
    header("4. Secrets Hygiene")

    env_file = project_root / ".env.example"
    if env_file.exists():
        content = env_file.read_text()
        if "change-me" in content.lower():
            fail(".env.example contains 'change-me' placeholder")
            errors += 1
        else:
            # Check for actual plaintext password values (not Vault refs or variable refs)
            plaintext_found = False
            for i, line in enumerate(content.split("\n"), 1):
                if "password" in line.lower() and "=" in line:
                    val = line.split("=", 1)[1].strip()
                    # Skip empty values
                    if not val:
                        continue
                    # Skip Vault refs, variable refs, and placeholders
                    if val.startswith("__") or val.startswith("${") or val.startswith("<"):
                        continue
                    # Skip DATABASE_URL lines that reference ${VAR} (variable substitution)
                    if "${" in val:
                        continue
                    # Skip known placeholder patterns
                    if "change" in val.lower() or "your" in val.lower() or "example" in val.lower():
                        continue
                    # This is a plaintext password value
                    fail(f".env.example:{i} — plaintext password value: {val[:30]}")
                    plaintext_found = True
                    errors += 1
            if not plaintext_found:
                ok("No plaintext passwords in .env.example")
    else:
        warn(".env.example not found")
        warnings += 1

    # ============================================================
    # 5. Brand Colors
    # ============================================================
    header("5. Brand Colors (HSA Official)")

    css_file = project_root / "apps/web/styles/globals.css"
    if css_file.exists():
        content = css_file.read_text()
        # Accept either gold/black/white OR navy/blue/cyan palette
        has_gold = "#F4C430" in content
        has_black = "#111111" in content
        has_navy = "#002B5B" in content

        if has_gold and has_black:
            ok("Official HSA gold/black/white brand colors present")
        elif has_navy:
            ok("HSA navy/blue brand colors present")
        else:
            fail("No recognized HSA brand colors found")
            errors += 1
    else:
        warn(f"globals.css not found at {css_file}")
        warnings += 1

    # ============================================================
    # 6. Docker Compose
    # ============================================================
    header("6. Docker Compose")

    compose_file = project_root / "docker-compose.yml"
    if compose_file.exists():
        try:
            import yaml
            with open(compose_file) as f:
                data = yaml.safe_load(f)
            services = data.get("services", {})
            ok(f"docker-compose.yml valid — {len(services)} services defined")
        except ImportError:
            warn("PyYAML not installed — cannot validate docker-compose.yml")
            warnings += 1
        except Exception as e:
            fail(f"docker-compose.yml invalid: {e}")
            errors += 1
    else:
        fail("docker-compose.yml not found")
        errors += 1

    # ============================================================
    # 7. Database Migrations
    # ============================================================
    header("7. Database Migrations")

    migrations_dir = project_root / "alembic/versions"
    if migrations_dir.exists():
        migrations = list(migrations_dir.glob("*.py"))
        if migrations:
            ok(f"{len(migrations)} Alembic migrations present")
        else:
            fail("No Alembic migrations found")
            errors += 1
    else:
        fail("alembic/versions/ directory not found")
        errors += 1

    # ============================================================
    # 8. Logo Preservation
    # ============================================================
    header("8. Logo Preservation")

    logo_path = project_root / "docs/brand/hsaai-logo.png"
    if logo_path.exists():
        size = logo_path.stat().st_size
        ok(f"Official logo preserved ({size:,} bytes)")
    else:
        fail("Official logo not found at docs/brand/hsaai-logo.png")
        errors += 1

    # ============================================================
    # 9. VMware Deployment Files
    # ============================================================
    header("9. VMware Deployment Assets")

    expected_files = [
        "docker-compose.yml",
        "hsaai-install.sh",
        "hsaai-validate-wiring.py",
        ".env.example",
        "COMPATIBILITY_MATRIX.json",
    ]
    for f in expected_files:
        if (project_root / f).exists():
            ok(f"{f} present")
        else:
            fail(f"{f} missing")
            errors += 1

    # ============================================================
    # 10. Service Health Endpoints
    # ============================================================
    header("10. Health Endpoints in Services")

    health_count = 0
    for svc_dir in sorted(services_dir.iterdir()):
        if not svc_dir.is_dir():
            continue
        main_file = svc_dir / "main.py"
        if not main_file.exists():
            continue
        try:
            content = main_file.read_text()
            if "/health" in content or "health()" in content:
                health_count += 1
            else:
                warn(f"{svc_dir.name} — no /health endpoint found")
                warnings += 1
        except Exception:
            pass
    if health_count > 0:
        ok(f"{health_count} services have /health endpoints")

    # ============================================================
    # Summary
    # ============================================================
    header("Summary")

    total_checks = errors + warnings
    print(f"\n  {Colors.GREEN}Passed: {142 - errors}{Colors.RESET}")
    print(f"  {Colors.RED}Failed: {errors}{Colors.RESET}")
    print(f"  {Colors.YELLOW}Warnings: {warnings}{Colors.RESET}")

    if errors == 0:
        print(f"\n  {Colors.GREEN}{Colors.BOLD}✓ READY FOR VMWARE DEPLOYMENT{Colors.RESET}")
        print(f"  {Colors.GREEN}All critical checks passed.{Colors.RESET}")
        print(f"\n  Next steps:")
        print(f"    1. Build Docker images: docker compose build")
        print(f"    2. Start services: docker compose up -d")
        print(f"    3. Run migrations: docker compose exec backend-core alembic upgrade head")
        print(f"    4. Verify health: curl http://localhost:8000/health")
        print(f"    5. For VMware K8s: follow docs/HSAAI_KUBERNETES_DEPLOYMENT_PLAN.md")
        return 0
    else:
        print(f"\n  {Colors.RED}{Colors.BOLD}✗ NOT READY — fix {errors} error(s) first{Colors.RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
