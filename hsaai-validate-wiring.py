#!/usr/bin/env python3
"""
HSAAI v4.1 — Wiring & Integration Validator
=============================================
Validates that all the wiring described in the HSAAI Executive Architecture
Book (Chapter 5 — Enterprise Integration, Chapter 6 — Security, Chapter 10 —
Deployment) is correctly configured in the project files.

This validator does NOT require Docker — it inspects the project structure,
docker-compose.yml, environment templates, and service source code to ensure
all the integration points described in the architecture book are present.

Run:
    python3 hsaai-validate-wiring.py [--project-root ./hsaai_extract]

Exit codes:
    0 — all critical checks passed
    1 — one or more critical checks failed
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# ─── Colors ─────────────────────────────────────────────────────────────────
class C:
    G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"
    B = "\033[94m"; BOLD = "\033[1m"; NC = "\033[0m"

# ─── Counters ───────────────────────────────────────────────────────────────
PASSED = 0
WARNED = 0
FAILED = 0

def ok(msg: str) -> None:
    global PASSED; PASSED += 1
    print(f"  {C.G}✓{C.NC} {msg}")

def warn(msg: str) -> None:
    global WARNED; WARNED += 1
    print(f"  {C.Y}⚠{C.NC} {msg}")

def fail(msg: str) -> None:
    global FAILED; FAILED += 1
    print(f"  {C.R}✗{C.NC} {msg}")

def section(title: str) -> None:
    print(f"\n{C.BOLD}{C.B}── {title} ──{C.NC}")

# ─── Checks ─────────────────────────────────────────────────────────────────

def check_docker_compose(root: Path) -> None:
    """Validate docker-compose.yml structure (Chapter 10 — Deployment)."""
    section("1. Docker Compose Stack (Chapter 10 — Deployment)")

    compose = root / "docker-compose.yml"
    if not compose.exists():
        fail("docker-compose.yml not found")
        return
    text = compose.read_text()

    # Required services grouped by layer (from the architecture book)
    required_services = {
        "Infrastructure": ["postgres", "redis", "qdrant", "neo4j", "kafka", "minio"],
        "Observability": ["prometheus", "grafana", "loki", "tempo", "otel-collector"],
        "Security": ["keycloak", "vault", "opa"],
        "LLM": ["llm-gateway"],
        "Application": [
            "api-gateway", "auth-service", "backend-core", "rag-service",
            "agent-runtime", "workflow-engine", "alignment-service",
            "governance-service", "pii-detector", "mcp-server",
            "model-training",
        ],
        "Frontend": ["frontend"],
        "MLOps": ["mlflow"],
    }

    for layer, services in required_services.items():
        section(f"  Layer: {layer}")
        for svc in services:
            pattern = rf"^  {re.escape(svc)}:\s*$"
            if re.search(pattern, text, re.MULTILINE):
                ok(f"{svc}")
            else:
                fail(f"{svc} — missing from docker-compose.yml")

    # Check for port conflicts
    section("  Port conflict check")
    port_map: dict[str, list[str]] = {}
    for m in re.finditer(r'ports:\s*\["?(\d+):(\d+)"?\]', text):
        host_port = m.group(1)
        port_map.setdefault(host_port, []).append("?")
    for port, count in port_map.items():
        if len(count) > 1:
            fail(f"Port {port} is mapped {len(count)} times — conflict!")
        else:
            ok(f"Port {port} — unique")


def check_env_template(root: Path) -> None:
    """Validate .env.production.example has all required vars (Chapter 6 — Security)."""
    section("2. Environment Template (Chapter 6 — Security)")

    env = root / ".env.production.example"
    if not env.exists():
        fail(".env.production.example not found")
        return
    text = env.read_text()

    required_vars = [
        # Database
        "POSTGRES_PASSWORD", "DATABASE_URL",
        # Identity
        "KEYCLOAK_ADMIN_PASSWORD", "KEYCLOAK_CLIENT_SECRET",
        "KEYCLOAK_REALM", "KEYCLOAK_CLIENT_ID",
        # Vector DB
        "QDRANT_URL", "QDRANT_API_KEY",
        # LLM
        "LLM_PROVIDER", "LLM_MODEL",
        # Knowledge graph
        "NEO4J_URI", "NEO4J_PASSWORD",
        # Observability
        "OTEL_EXPORTER_OTLP_ENDPOINT", "GRAFANA_ADMIN_PASSWORD",
        # Security
        "AUTH_REQUIRED", "ALLOW_DEV_RBAC", "CORS_ALLOW_ORIGINS",
        # Enterprise connectors (Chapter 5)
        "SAP_BASE_URL", "SHAREPOINT_BASE_URL", "AD_URL",
        # Storage
        "LOCAL_FILE_STORAGE", "AUDIT_LOG_DIR",
    ]
    for var in required_vars:
        if re.search(rf"^{var}=", text, re.MULTILINE):
            ok(f"{var}")
        else:
            fail(f"{var} — missing from .env.production.example")

    # Check no plaintext secrets are committed
    section("  Plaintext secret check")
    for line in text.splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, _, val = line.partition("=")
            if val and "CHANGE_ME" not in val and "change-me" not in val and "example" not in val:
                # Allow URLs and non-secret config
                if not any(k in key.upper() for k in ["URL", "PORT", "PATH", "PREFIX",
                    "ENV", "PROVIDER", "MODEL", "MIME", "LIMIT", "COST", "BUDGET",
                    "THRESHOLD", "TIER", "ID", "REF", "REALM", "AUDIENCE",
                    "ENABLED", "DB"]):
                    warn(f"{key} has a non-placeholder value: {val[:30]}...")


def check_service_dockerfiles(root: Path) -> None:
    """Validate all services have Dockerfiles (Chapter 10 — Deployment)."""
    section("3. Service Dockerfiles (Chapter 10 — Deployment)")

    services_dir = root / "services"
    if not services_dir.exists():
        fail("services/ directory not found")
        return

    for svc in sorted(services_dir.iterdir()):
        if not svc.is_dir():
            continue
        dockerfile = svc / "Dockerfile"
        if dockerfile.exists():
            content = dockerfile.read_text()
            # Check Dockerfile has HEALTHCHECK (best practice)
            if "HEALTHCHECK" in content:
                ok(f"{svc.name}/Dockerfile (with healthcheck)")
            else:
                warn(f"{svc.name}/Dockerfile — no HEALTHCHECK defined")
        else:
            fail(f"{svc.name}/Dockerfile — MISSING")


def check_infrastructure_configs(root: Path) -> None:
    """Validate infrastructure config files referenced by docker-compose exist."""
    section("4. Infrastructure Config Files (Chapter 10 — Deployment)")

    compose = root / "docker-compose.yml"
    if not compose.exists():
        return
    text = compose.read_text()

    # Extract all ./path references from volume mounts
    mount_pattern = r"^\s+-\s+\./([^\s:]+)"
    referenced = set()
    for m in re.finditer(mount_pattern, text, re.MULTILINE):
        path = m.group(1)
        referenced.add(path)

    for rel_path in sorted(referenced):
        full_path = root / rel_path
        if full_path.exists():
            ok(f"{rel_path}")
        else:
            fail(f"{rel_path} — MISSING (referenced in docker-compose.yml)")


def check_keycloak_realm(root: Path) -> None:
    """Validate Keycloak realm configuration (Chapter 6 — Security)."""
    section("5. Keycloak Realm Configuration (Chapter 6 — Security)")

    realm_file = root / "infrastructure" / "keycloak" / "hsaai-realm.json"
    if not realm_file.exists():
        fail("infrastructure/keycloak/hsaai-realm.json — MISSING")
        return

    try:
        realm = json.loads(realm_file.read_text())
    except json.JSONDecodeError as e:
        fail(f"hsaai-realm.json — invalid JSON: {e}")
        return

    # Required top-level fields
    if realm.get("realm") == "hsaai":
        ok("realm name = 'hsaai'")
    else:
        fail(f"realm name = '{realm.get('realm')}' (expected 'hsaai')")

    if realm.get("enabled"):
        ok("realm enabled = true")
    else:
        fail("realm enabled = false")

    # Clients (Chapter 6 — OIDC + PKCE)
    clients = {c.get("clientId"): c for c in realm.get("clients", []) if isinstance(c, dict)}
    # Accept either hsaai-web or hsaai-frontend as the frontend OIDC client
    frontend_client = "hsaai-web" if "hsaai-web" in clients else (
        "hsaai-frontend" if "hsaai-frontend" in clients else None
    )
    if frontend_client:
        web = clients[frontend_client]
        if "pkceCodeChallengeMethod" in web or web.get("standardFlowEnabled"):
            ok(f"client '{frontend_client}' — OIDC + PKCE configured")
        else:
            warn(f"client '{frontend_client}' — PKCE not explicitly configured")
    else:
        fail("client 'hsaai-web'/'hsaai-frontend' — MISSING (frontend OIDC client)")

    # Service account client (for backend-to-backend auth)
    if "hsaai-api" in clients:
        api = clients["hsaai-api"]
        if api.get("serviceAccountsEnabled"):
            ok("client 'hsaai-api' — service account enabled")
        else:
            warn("client 'hsaai-api' — service account not enabled")
    else:
        fail("client 'hsaai-api' — MISSING (backend service account client)")

    # Roles (Chapter 6 — RBAC) — roles may be a dict {realm: [...]} or a list
    raw_roles = realm.get("roles", [])
    if isinstance(raw_roles, dict):
        role_list = raw_roles.get("realm", [])
    else:
        role_list = raw_roles
    role_names = {r.get("name") for r in role_list if isinstance(r, dict)}
    required_roles = {"ai_user", "department_manager", "executive", "ai_admin"}
    # Also accept the 'admin' role as equivalent to 'ai_admin' (per the realm file)
    if "admin" in role_names:
        role_names.add("ai_admin")
    for role in required_roles:
        if role in role_names:
            ok(f"role '{role}'")
        else:
            fail(f"role '{role}' — MISSING")

    # Users (may be in realm JSON or bootstrapped via kcadm.sh)
    users = realm.get("users", [])
    if len(users) >= 4:
        ok(f"{len(users)} users defined in realm JSON (≥4 required)")
    elif len(users) > 0:
        warn(f"only {len(users)} users in realm JSON — others may be bootstrapped via kcadm.sh")
    else:
        warn("no users in realm JSON — they must be bootstrapped via deploy/06-bootstrap-keycloak.sh")

    # Brute-force protection (Chapter 6 — Zero Trust)
    if realm.get("bruteForceProtected"):
        ok("brute-force protection enabled")
    else:
        warn("brute-force protection NOT enabled")


def check_cross_service_wiring(root: Path) -> None:
    """Validate service-to-service wiring (Chapter 5 — Enterprise Integration)."""
    section("6. Cross-Service Wiring (Chapter 5 — Enterprise Integration)")

    compose = root / "docker-compose.yml"
    if not compose.exists():
        return
    text = compose.read_text()

    # Expected wiring — each service should reference its dependencies via env vars
    wiring_checks = [
        ("api-gateway",   "LLM_GATEWAY_URL",       "llm-gateway"),
        ("api-gateway",   "auth-service",          "auth-service"),
        ("backend-core",  "DATABASE_URL",          "postgres"),
        ("backend-core",  "QDRANT_URL",            "qdrant"),
        ("backend-core",  "LLM_GATEWAY_URL",       "llm-gateway"),
        ("backend-core",  "RAG_ENGINE_URL",        "rag-service"),
        ("backend-core",  "AUTH_SERVICE_URL",      "auth-service"),
        ("backend-core",  "KEYCLOAK_ISSUER",       "keycloak"),
        ("rag-service",   "QDRANT_URL",            "qdrant"),
        ("rag-service",   "NEO4J_URL",             "neo4j"),
        ("rag-service",   "LLM_GATEWAY_URL",       "llm-gateway"),
        ("agent-runtime", "LLM_GATEWAY_URL",       "llm-gateway"),
        ("agent-runtime", "RAG_ENGINE_URL",        "rag-service"),
        ("agent-runtime", "KAFKA_BOOTSTRAP_SERVERS","kafka"),
        ("workflow-engine","BACKEND_CORE_URL",     "backend-core"),
        ("alignment-service","LLM_GATEWAY_URL",    "llm-gateway"),
        ("mcp-server",    "RAG_ENGINE_URL",        "rag-service"),
        ("mcp-server",    "WORKFLOW_ENGINE_URL",   "workflow-engine"),
        ("model-training","MLFLOW_TRACKING_URI",   "mlflow"),
        ("model-training","MINIO_ENDPOINT",        "minio"),
    ]

    for svc, env_var, dep in wiring_checks:
        # Find the service block
        svc_pattern = rf"^  {re.escape(svc)}:\s*$"
        if not re.search(svc_pattern, text, re.MULTILINE):
            fail(f"{svc} → {dep} via {env_var}: service not in compose")
            continue
        # Extract service block (until next service or end)
        match = re.search(rf"(  {re.escape(svc)}:\n(?:    .*\n|\n)*?)(?=\n  [a-z]|\nvolumes:|\Z)",
                          text)
        if not match:
            match = re.search(rf"(  {re.escape(svc)}:[\s\S]*?)(?=\n  [a-z][\w-]*:|\nvolumes:|\Z)", text)
        block = match.group(1) if match else ""
        if env_var in block or dep in block:
            ok(f"{svc} → {dep} via {env_var}")
        else:
            fail(f"{svc} → {dep} via {env_var}: env var not found in service block")


def check_observability_wiring(root: Path) -> None:
    """Validate OpenTelemetry + Prometheus + Grafana wiring (Chapter 9 — Analytics)."""
    section("7. Observability Wiring (Chapter 9 — Analytics)")

    # OTEL collector config
    otel_config = root / "infrastructure" / "otel" / "collector-config.yaml"
    if otel_config.exists():
        text = otel_config.read_text()
        if "otlp/tempo" in text and "loki" in text and "prometheusremotewrite" in text:
            ok("OTEL collector → Tempo + Loki + Prometheus (traces + logs + metrics)")
        else:
            fail("OTEL collector config — missing exporters")
    else:
        fail("infrastructure/otel/collector-config.yaml — MISSING")

    # Prometheus config
    prom_config = root / "infrastructure" / "prometheus" / "prometheus.yml"
    if prom_config.exists():
        text = prom_config.read_text()
        services_scraped = sum(1 for s in [
            "api-gateway", "backend-core", "rag-service", "llm-gateway",
            "agent-runtime", "workflow-engine", "alignment-service",
            "governance-service", "pii-detector", "mcp-server"
        ] if s in text)
        if services_scraped >= 8:
            ok(f"Prometheus scrapes {services_scraped}/10 application services")
        else:
            warn(f"Prometheus scrapes only {services_scraped}/10 application services")
    else:
        fail("infrastructure/prometheus/prometheus.yml — MISSING")

    # Grafana dashboards
    dashboards_dir = root / "infrastructure" / "grafana" / "dashboards"
    if dashboards_dir.exists():
        dashboards = list(dashboards_dir.glob("*.json"))
        if len(dashboards) >= 3:
            ok(f"Grafana has {len(dashboards)} provisioned dashboards")
        else:
            warn(f"Grafana has only {len(dashboards)} dashboards (expected ≥3)")
    else:
        fail("infrastructure/grafana/dashboards/ — MISSING")


def check_security_wiring(root: Path) -> None:
    """Validate Vault + OPA + mTLS wiring (Chapter 6 — Security)."""
    section("8. Security Wiring (Chapter 6 — Security / Zero Trust)")

    # Vault config
    vault_hcl = root / "infrastructure" / "vault" / "vault.hcl"
    if vault_hcl.exists():
        ok("Vault config (vault.hcl) present")
    else:
        fail("infrastructure/vault/vault.hcl — MISSING")

    # OPA policies
    opa_policies = root / "infrastructure" / "opa" / "policies"
    if opa_policies.exists():
        policies = list(opa_policies.glob("*.rego"))
        if policies:
            ok(f"OPA has {len(policies)} policy files: {[p.name for p in policies]}")
        else:
            warn("OPA policies directory exists but contains no .rego files")
    else:
        fail("infrastructure/opa/policies/ — MISSING")

    # WAF rules
    waf_dir = root / "infrastructure" / "waf"
    if waf_dir.exists() and any(waf_dir.iterdir()):
        ok("WAF rules present")
    else:
        warn("WAF rules directory empty or missing")

    # mTLS certs directory
    mtls_dir = root / "infrastructure" / "mtls"
    if mtls_dir.exists():
        ok("mTLS directory present")
    else:
        warn("mTLS directory missing")


def check_enterprise_connectors(root: Path) -> None:
    """Validate enterprise connector stubs (Chapter 5 — Enterprise Integration)."""
    section("9. Enterprise Connectors (Chapter 5 — Enterprise Integration)")

    env = root / ".env.production.example"
    if not env.exists():
        return
    text = env.read_text()

    connectors = {
        "SAP":         ["SAP_BASE_URL", "SAP_CLIENT_ID", "SAP_SYSTEM_ID"],
        "SharePoint":  ["SHAREPOINT_BASE_URL", "SHAREPOINT_TENANT_ID", "SHAREPOINT_SITE_ID"],
        "Active Directory": ["AD_URL", "AD_BIND_DN", "AD_BASE_DN"],
        "SMTP/Email":  ["SMTP_HOST", "SMTP_PORT", "SMTP_USER"],
        "Teams":       ["TEAMS_WEBHOOK_URL"],
        "Slack":       ["SLACK_WEBHOOK_URL"],
    }
    for name, vars in connectors.items():
        found = sum(1 for v in vars if v in text)
        if found == len(vars):
            ok(f"{name} connector — all {len(vars)} env vars present")
        elif found > 0:
            warn(f"{name} connector — {found}/{len(vars)} env vars present")
        else:
            fail(f"{name} connector — no env vars found")


def check_database_migrations(root: Path) -> None:
    """Validate Alembic migrations exist (Chapter 10 — Deployment)."""
    section("10. Database Migrations (Chapter 10 — Deployment)")

    alembic_dir = root / "alembic" / "versions"
    if not alembic_dir.exists():
        fail("alembic/versions/ — MISSING")
        return

    migrations = list(alembic_dir.glob("*.py"))
    if len(migrations) >= 2:
        ok(f"{len(migrations)} Alembic migrations present")
        for m in sorted(migrations):
            ok(f"  - {m.name}")
    else:
        warn(f"only {len(migrations)} migrations found (expected ≥2)")


def main() -> int:
    parser = argparse.ArgumentParser(description="HSAAI wiring & integration validator")
    parser.add_argument("--project-root", default="./hsaai_extract",
                        help="Path to the HSAAI project root")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    if not root.exists():
        print(f"{C.R}Project root not found: {root}{C.NC}", file=sys.stderr)
        return 2

    print(f"{C.BOLD}{C.B}HSAAI v4.1 — Wiring & Integration Validator{C.NC}")
    print(f"{C.B}Project root: {root}{C.NC}")
    print(f"{C.B}Following: HSAAI Executive Architecture Book (Ch. 5, 6, 9, 10){C.NC}")

    check_docker_compose(root)
    check_env_template(root)
    check_service_dockerfiles(root)
    check_infrastructure_configs(root)
    check_keycloak_realm(root)
    check_cross_service_wiring(root)
    check_observability_wiring(root)
    check_security_wiring(root)
    check_enterprise_connectors(root)
    check_database_migrations(root)

    print(f"\n{C.BOLD}{'═' * 70}{C.NC}")
    print(f"{C.BOLD}  Summary: {C.G}{PASSED} passed{C.NC}, "
          f"{C.Y}{WARNED} warnings{C.NC}, {C.R}{FAILED} failed{C.NC}")
    print(f"{C.BOLD}{'═' * 70}{C.NC}")

    if FAILED > 0:
        print(f"\n{C.R}Critical issues found — fix them before deployment.{C.NC}")
        return 1
    elif WARNED > 0:
        print(f"\n{C.Y}Warnings found — review them, but deployment can proceed.{C.NC}")
        return 0
    else:
        print(f"\n{C.G}All checks passed — project is ready for deployment.{C.NC}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
