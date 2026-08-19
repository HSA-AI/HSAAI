"""
HSAAI Security Regression Tests (v4.0)
Ensures security fixes are never regressed.
"""
import pytest
import os
import re
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class TestNoBearerAdminFallback:
    """Ensure no TS file uses 'Bearer admin' or 'Bearer hsaai_admin' fallback."""

    def test_no_bearer_admin_in_ts(self):
        results = subprocess.run(
            ["rg", "-l", r"Bearer\s+(admin|hsaai_admin)\b", "--type", "ts",
             "--glob", "!**/lib/server-auth.ts", "apps/web/"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
        assert results.returncode != 0 or not results.stdout.strip(), \
            f"Found Bearer admin/hsaai_admin in TS files:\n{results.stdout}"

    def test_no_bearer_admin_in_js(self):
        results = subprocess.run(
            ["rg", "-l", r"Bearer\s+(admin|hsaai_admin)\b", "--type", "js",
             "apps/web/", "services/"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
        assert results.returncode != 0 or not results.stdout.strip()


class TestNoDevBypassFlags:
    """Ensure ALLOW_DEV_RBAC and ALLOW_DEV_AUTH are never true."""

    def test_no_allow_dev_rbac(self):
        results = subprocess.run(
            ["rg", "-n", r"ALLOW_DEV_RBAC.*true", "--type", "py", "services/", "packages/"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
        assert not results.stdout.strip(), \
            f"ALLOW_DEV_RBAC enabled:\n{results.stdout}"

    def test_no_allow_dev_auth(self):
        results = subprocess.run(
            ["rg", "-n", r"ALLOW_DEV_AUTH.*true", "--type", "py", "services/"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
        assert not results.stdout.strip()


class TestNoHardcodedSecrets:
    """Ensure no hardcoded passwords or API keys in source."""

    PATTERNS = [
        r'''password\s*=\s*['"][^'"]{3,}['"]''',
        r'''api_key\s*=\s*['"][^'"]{10,}['"]''',
        r'''secret\s*=\s*['"][^'"]{10,}['"]''',
        r'''sk-[a-zA-Z0-9]{32,}''',
        r'''ghp_[a-zA-Z0-9]{36}''',
        r'''AKIA[A-Z0-9]{16}''',
    ]

    def test_no_hardcoded_secrets(self):
        violations = []
        for py_file in (PROJECT_ROOT / "services").rglob("*.py"):
            if "_deprecated" in str(py_file) or "__pycache__" in str(py_file):
                continue
            content = py_file.read_text(errors="ignore")
            for pattern in self.PATTERNS:
                matches = re.findall(pattern, content)
                if matches:
                    # Exclude env var references and test fixtures
                    real_matches = [m for m in matches if "os.getenv" not in m and "test" not in m.lower()]
                    if real_matches:
                        violations.append(f"{py_file}: {real_matches[:2]}")
        assert not violations, f"Hardcoded secrets found:\n{chr(10).join(violations[:10])}"


class TestNoSqlInjection:
    """Check for SQL injection patterns in Python code."""

    def test_no_fstring_sql(self):
        results = subprocess.run(
            ["rg", "-n", r'f["\']SELECT|f["\']INSERT|f["\']UPDATE|f["\']DELETE',
             "--type", "py", "services/"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
        # Allow text() calls with :param style
        violations = []
        for line in results.stdout.split("\n"):
            if not line:
                continue
            # Skip safe patterns (parameterized queries)
            if ":param" in line or ":tenant_id" in line or ":start" in line:
                continue
            violations.append(line)
        assert not violations, f"Potential SQL injection:\n{chr(10).join(violations[:5])}"


class TestPathTraversalProtection:
    """Ensure path traversal protection is in place."""

    def test_dataset_upload_has_secure_filename(self):
        filepath = PROJECT_ROOT / "services" / "model_training" / "api" / "dataset_routes.py"
        content = filepath.read_text()
        assert "secure_filename" in content, "Dataset upload missing secure_filename"
        assert "ALLOWED_NAME_PATTERN" in content, "Dataset upload missing name validation"
        assert "relative_to(dest_dir.resolve())" in content, "Dataset upload missing path check"

    def test_rag_upload_has_secure_name(self):
        filepath = PROJECT_ROOT / "services" / "rag_engine" / "main.py"
        content = filepath.read_text()
        assert "def secure_name" in content, "RAG upload missing secure_name function"


class TestAuthOnAllServices:
    """Ensure all microservices have auth dependency."""

    SERVICES = [
        "rag_engine/main.py",
        "llm_gateway/main.py",
        "multi_agents/main.py",
        "ai_orchestrator/main.py",
        "workflow_engine/main.py",
        "document_ai/main.py",
        "voice_ai/main.py",
        "analytics/main.py",
    ]

    def test_all_services_have_auth(self):
        missing = []
        for svc in self.SERVICES:
            filepath = PROJECT_ROOT / "services" / svc
            if not filepath.exists():
                continue
            content = filepath.read_text()
            if "verify_service_auth" not in content and "_auth_dep" not in content:
                missing.append(svc)
        assert not missing, f"Services without auth: {missing}"


class TestPromptInjectionDefense:
    """Ensure prompt injection defense is active."""

    def test_rag_engine_uses_sanitizer(self):
        filepath = PROJECT_ROOT / "services" / "rag_engine" / "main.py"
        content = filepath.read_text()
        assert "sanitize_user_query" in content or "prompt_security" in content, \
            "RAG engine missing prompt injection defense"

    def test_prompt_security_module_exists(self):
        filepath = PROJECT_ROOT / "packages" / "common" / "prompt_security" / "__init__.py"
        assert filepath.exists(), "prompt_security module missing"
        content = filepath.read_text()
        assert "INJECTION_PATTERNS" in content
        assert "sanitize_user_query" in content
        assert "build_safe_prompt" in content


class TestPIIDetection:
    """Ensure PII detection is wired into RAG upload."""

    def test_rag_upload_calls_pii_detector(self):
        filepath = PROJECT_ROOT / "services" / "rag_engine" / "main.py"
        content = filepath.read_text()
        assert "pii_detector" in content, "RAG upload not calling PII detector"


class TestNoSilentExceptions:
    """Ensure no bare 'except: pass' in production code."""

    def test_no_silent_exceptions(self):
        results = subprocess.run(
            ["rg", "-n", r"except\s*(Exception|BaseException)?\s*:\s*pass", "--type", "py", "services/"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
        # Allow in explicitly safe contexts (logging already covers them)
        violations = []
        for line in results.stdout.split("\n"):
            if not line:
                continue
            # Skip approvals (v2.0 fixed with logging)
            if "approvals/service.py" in line and "FIX" in line:
                continue
            violations.append(line)
        assert not violations, f"Silent exceptions found:\n{chr(10).join(violations[:10])}"


class TestDockerComposeSecurity:
    """Ensure docker-compose files are hardened."""

    def test_keycloak_not_start_dev(self):
        for compose_file in ["docker-compose.hsa-internal.yml", "docker-compose.production.yml"]:
            filepath = PROJECT_ROOT / compose_file
            if not filepath.exists():
                continue
            content = filepath.read_text()
            assert "start-dev" not in content, f"{compose_file} still uses start-dev"

    def test_neo4j_not_exposed_to_host(self):
        for compose_file in ["docker-compose.hsa-internal.yml", "docker-compose.production.yml"]:
            filepath = PROJECT_ROOT / compose_file
            if not filepath.exists():
                continue
            content = filepath.read_text()
            # Should use expose: not ports: for Neo4j
            assert "7474:7474" not in content, f"{compose_file} exposes Neo4j to host"

    def test_elasticsearch_security_enabled(self):
        for compose_file in ["docker-compose.hsa-internal.yml", "docker-compose.production.yml"]:
            filepath = PROJECT_ROOT / compose_file
            if not filepath.exists():
                continue
            content = filepath.read_text()
            assert "xpack.security.enabled: 'true'" in content or "xpack.security.enabled: \"true\"" in content, \
                f"{compose_file} has ES security disabled"
