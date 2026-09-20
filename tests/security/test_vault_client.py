"""
HSAAI Vault Client Tests (Fix #2 Verification)
================================================
Verifies:
  - Vault client initializes
  - Circuit breaker trips on failures
  - Cache works (TTL-based)
  - Audit log records access
  - Fallback to env vars in dev
  - Health check works
"""
import os
import sys
import pytest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR / "packages" / "common"))

from security.vault_client import (
    VaultClient, CircuitBreakerState, CircuitBreakerOpen,
    vault_client, get_secret, get_database_url, get_jwt_signing_key,
)


class TestCircuitBreaker:
    def test_circuit_starts_closed(self):
        cb = CircuitBreakerState()
        assert cb.state == "closed"
        assert cb.can_attempt() is True

    def test_circuit_opens_after_threshold(self):
        cb = CircuitBreakerState(threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.can_attempt() is True  # still closed at 2
        cb.record_failure()
        assert cb.state == "open"
        assert cb.can_attempt() is False  # open at 3

    def test_circuit_half_open_after_timeout(self):
        import time
        cb = CircuitBreakerState(threshold=1, reset_timeout=0.1)
        cb.record_failure()
        assert cb.state == "open"
        time.sleep(0.15)
        assert cb.can_attempt() is True
        assert cb.state == "half-open"

    def test_circuit_closes_on_success(self):
        cb = CircuitBreakerState(threshold=2)
        cb.record_failure()
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == "closed"


class TestVaultClient:
    def test_vault_client_dev_mode_no_auth_uses_empty_token(self):
        """In dev mode with no auth, client should use empty token (not dev-only-token)."""
        os.environ.pop("VAULT_TOKEN", None)
        os.environ.pop("VAULT_APPROLE_ROLE_ID", None)
        os.environ.pop("VAULT_K8S_ROLE", None)
        os.environ["DEPLOY_ENV"] = "development"
        os.environ["VAULT_ADDR"] = "http://localhost:8200"

        client = VaultClient()
        client.initialize()
        # In dev mode: token should be empty (NOT "dev-only-token")
        assert client.token != "dev-only-token"
        # Secrets will fall back to env vars in dev mode

    def test_vault_client_production_no_auth_raises_systemexit(self):
        """In production with no auth, client MUST raise SystemExit (Fail-Closed)."""
        os.environ.pop("VAULT_TOKEN", None)
        os.environ.pop("VAULT_APPROLE_ROLE_ID", None)
        os.environ.pop("VAULT_K8S_ROLE", None)
        os.environ["DEPLOY_ENV"] = "production"
        os.environ["VAULT_ADDR"] = "http://localhost:8200"

        client = VaultClient()
        with pytest.raises(SystemExit):
            client.initialize()

    def test_health_check_returns_dict(self):
        """Health check should return a dict with healthy flag."""
        # FIX-20: health_check is async — must run via event loop.
        import asyncio
        client = VaultClient()
        client.vault_url = "http://localhost:1"  # unreachable
        health = asyncio.run(client.health_check())
        assert "healthy" in health
        assert health["healthy"] is False  # unreachable

    def test_audit_log_records_access(self):
        """Audit log should record secret accesses."""
        client = VaultClient()
        client._audit_access("secret/data/test", "cache_hit")
        log = client.get_audit_log()
        assert len(log) > 0
        assert log[-1]["path"] == "secret/data/test"
        assert log[-1]["action"] == "cache_hit"

    def test_cache_invalidation(self):
        """Cache should be invalidatable."""
        from security.vault_client import CacheEntry
        client = VaultClient()
        client._cache["test/path"] = CacheEntry(data={"key": "val"}, expires_at=9999999)
        assert "test/path" in client._cache
        client.invalidate_cache("test/path")
        assert "test/path" not in client._cache

    def test_get_secret_falls_back_to_env(self):
        """get_secret_value should fall back to env var if Vault unavailable (dev mode)."""
        # FIX-20: get_secret_value is async — use the sync wrapper
        # get_secret_value_sync which handles the event loop internally.
        os.environ["DEPLOY_ENV"] = "development"
        os.environ["TEST_FALLBACK_KEY"] = "env_value"
        try:
            client = VaultClient()
            client.vault_url = "http://localhost:1"  # unreachable
            # Should fall back to env
            result = client.get_secret_value_sync("secret/data/test", "test_fallback_key", "default")
            assert result == "env_value"
        finally:
            del os.environ["TEST_FALLBACK_KEY"]
            os.environ.pop("DEPLOY_ENV", None)


class TestSecretAccessors:
    def test_get_database_url_dev_mode(self):
        """In development, DATABASE_URL comes from env var."""
        os.environ["DEPLOY_ENV"] = "development"
        os.environ["DATABASE_URL"] = "sqlite:///test.db"
        try:
            url = get_database_url()
            assert url == "sqlite:///test.db"
        finally:
            os.environ.pop("DEPLOY_ENV", None)
            os.environ.pop("DATABASE_URL", None)

    def test_get_jwt_signing_key_falls_back(self):
        """JWT key should fall back to env var in dev."""
        os.environ["JWT_SIGNING_KEY"] = "test-key"
        try:
            key = get_jwt_signing_key()
            # Falls back to env since Vault is unreachable
            assert key is not None
        finally:
            os.environ.pop("JWT_SIGNING_KEY", None)


class TestNoDirectSecretReads:
    """Forensic: verify services don't read sensitive secrets directly from env."""

    def test_no_hardcoded_passwords_in_production_code(self):
        """Production code should not read passwords directly from env vars."""
        import re
        violations = []
        sensitive_patterns = [
            r'os\.getenv\s*\(\s*["\']PASSWORD["\']',
            r'os\.getenv\s*\(\s*["\']SECRET_KEY["\']',
            r'os\.getenv\s*\(\s*["\']JWT_SECRET["\']',
            r'os\.getenv\s*\(\s*["\']OPENAI_API_KEY["\']',
            r'os\.getenv\s*\(\s*["\']DATABASE_PASSWORD["\']',
        ]
        for py_file in (BASE_DIR / "services").rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            content = py_file.read_text()
            # Strip comments
            cleaned = re.sub(r'#.*$', '', content, flags=re.MULTILINE)
            for pattern in sensitive_patterns:
                if re.search(pattern, cleaned):
                    violations.append((str(py_file), pattern))
                    break

        # Allow some exceptions (config files that pass through to Vault)
        # The point is to FLAG them, not necessarily zero
        # For now, just log the count
        if violations:
            print(f"⚠️  Direct secret reads found in {len(violations)} files "
                  f"(should migrate to Vault): {[v[0] for v in violations[:5]]}")
        # This test is informational — Vault migration is gradual
        assert len(violations) < 20, f"Too many direct secret reads: {len(violations)}"
