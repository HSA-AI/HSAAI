#!/usr/bin/env python3
"""HSAAI internal-only production verifier.

Fails fast when the deployment contains external AI/API configuration, weak
placeholder secrets, missing internal runtime files, or unsafe production flags.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
BLOCKED_KEYS = {
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "MISTRAL_API_KEY",
    "COHERE_API_KEY",
    "PINECONE_API_KEY",
    "SENTRY_DSN",
}
SECRET_KEYS = {
    "POSTGRES_PASSWORD",
    "JWT_SECRET",
    "KEYCLOAK_ADMIN_PASSWORD",
    "QDRANT_API_KEY",
    "ENCRYPTION_KEY",
}
WEAK_VALUES = {"", "changeme", "change_me", "CHANGE_ME", "CHANGE_ME_STRONG_PASSWORD", "CHANGE_ME_64_CHARS", "password", "admin", "secret", "123456"}
ALLOWED_HOSTS = {
    "localhost", "127.0.0.1", "backend", "api_gateway", "api-gateway", "auth_service", "ai_orchestrator",
    "rag_engine", "llm_gateway", "local_llm", "postgres", "redis", "qdrant", "elasticsearch",
    "keycloak", "analytics", "prometheus", "grafana", "otel-collector", "ollama", "frontend",
}
URL_RE = re.compile(r"https?://[^\s\"'<>]+")
SCAN_FILES = [
    ".env.example",
    ".env.hsa-internal.example",
    ".env.production.example",
    "docker-compose.dev.yml",
    "docker-compose.hsa-internal.yml",
    "docker-compose.production.yml",
    "deployment/compose/docker-compose.internal.yml",
    "services/api_gateway/main.py",
    "services/llm_gateway/main.py",

    "services/backend_core/security/internal_only.py",
    "services/rag_engine/main.py",
    "deployment/kubernetes/network-policies/default-deny-egress.yaml",
    "deployment/kubernetes/network-policies/allow-internal-services.yaml",
]


def read_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw in path.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def host_allowed(url: str) -> bool:
    host = urlparse(url).hostname or ""
    if host in ALLOWED_HOSTS:
        return True
    if host.endswith(".svc") or host.endswith(".svc.cluster.local"):
        return True
    if host.endswith(".company.local") or host.endswith(".local"):
        return True
    return False


def weak_secret(value: str | None) -> bool:
    if value is None:
        return True
    stripped = value.strip()
    if stripped in WEAK_VALUES:
        return True
    if stripped.startswith("${") and ":?" in stripped:
        return False
    return len(stripped) < 16


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    for key in BLOCKED_KEYS:
        if os.getenv(key):
            errors.append(f"Environment variable {key} must be empty in internal-only mode")

    prod_env = read_env_file(ROOT / ".env.production.example")
    for key in SECRET_KEYS:
        value = os.getenv(key) or prod_env.get(key)
        if weak_secret(value):
            errors.append(f"Weak or placeholder production secret: {key}")

    for rel in SCAN_FILES:
        path = ROOT / rel
        if not path.exists():
            # Kubernetes files are optional in smaller bundles, but service/runtime files are not.
            if rel.startswith("deployment/kubernetes") or rel.startswith("deployment/compose"):
                warnings.append(f"Optional deployment file not found: {rel}")
                continue
            errors.append(f"Missing expected file: {rel}")
            continue
        text = path.read_text(errors="ignore")
        if "ALLOW_EXTERNAL_APIS=true" in text or "ALLOW_EXTERNAL_AI=true" in text:
            errors.append(f"Unsafe external API setting found in {rel}")
        for url in URL_RE.findall(text):
            clean = url.rstrip(".)],}")
            host = urlparse(clean).hostname or ""
            if host in {"docker.elastic.co", "quay.io", "docker.io", "ghcr.io"}:
                continue
            if not host_allowed(clean):
                errors.append(f"Potential external runtime URL in {rel}: {clean}")

    compose = (ROOT / "docker-compose.production.yml").read_text(errors="ignore") if (ROOT / "docker-compose.production.yml").exists() else ""
    required_prod_terms = ["healthcheck:", "AUTH_REQUIRED", "ALLOW_DEV_AUTH", "ALLOW_DEV_LOGIN", "RAG_ANSWER_USE_LLM", "LLM_GATEWAY_URL"]
    for term in required_prod_terms:
        if term not in compose:
            errors.append(f"Production compose missing required hardening term: {term}")

    if warnings:
        print("HSAAI internal-only verification warnings:\n")
        for w in warnings:
            print(f"- {w}")
        print()
    if errors:
        print("HSAAI internal-only verification FAILED:\n")
        for e in errors:
            print(f"- {e}")
        return 1
    print("HSAAI internal-only verification PASSED: strict internal runtime, strong-secret policy, and production hardening checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
