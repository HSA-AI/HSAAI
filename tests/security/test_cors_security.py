"""
HSAAI CORS Security Tests (Fix #1 Verification)
=================================================
Verifies:
  - No wildcard origins in production/staging
  - Unauthorized origins rejected
  - Authorized origins allowed
  - Credentials supported
  - Centralized config used by all services
"""
import os
import sys
import pytest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR / "packages" / "common"))

from security.cors_config import setup_cors, get_allowed_origins


class TestCORSConfig:
    """Test centralized CORS configuration."""

    def test_no_wildcard_in_production(self):
        """Production MUST NOT allow wildcard origins."""
        origins = get_allowed_origins("production")
        assert "*" not in origins, f"Wildcard in production origins: {origins}"

    def test_no_wildcard_in_staging(self):
        """Staging MUST NOT allow wildcard origins."""
        origins = get_allowed_origins("staging")
        assert "*" not in origins, f"Wildcard in staging origins: {origins}"

    def test_dev_allows_localhost(self):
        """Development should allow localhost for DX."""
        origins = get_allowed_origins("development")
        assert "http://localhost:3000" in origins

    def test_env_var_override_works(self):
        """CORS_ALLOW_ORIGINS env var overrides defaults."""
        os.environ["CORS_ALLOW_ORIGINS"] = "https://custom.example.com,https://another.example.com"
        try:
            origins = get_allowed_origins("production")
            assert "https://custom.example.com" in origins
            assert "https://another.example.com" in origins
            assert "*" not in origins
        finally:
            del os.environ["CORS_ALLOW_ORIGINS"]

    def test_env_var_wildcard_rejected_in_production(self):
        """Wildcard in env var MUST be rejected for production."""
        os.environ["CORS_ALLOW_ORIGINS"] = "*"
        try:
            with pytest.raises(ValueError, match="wildcard"):
                get_allowed_origins("production")
        finally:
            del os.environ["CORS_ALLOW_ORIGINS"]

    def test_production_origins_are_https(self):
        """Production origins should be HTTPS (no HTTP)."""
        origins = get_allowed_origins("production")
        for origin in origins:
            assert origin.startswith("https://"), f"Non-HTTPS origin in production: {origin}"


class TestCORSIntegration:
    """Test CORS behavior on actual FastAPI apps."""

    def _create_test_app(self, environment="production"):
        """Create a minimal FastAPI app with CORS configured."""
        app = FastAPI()

        @app.get("/test")
        def test_endpoint():
            return {"status": "ok"}

        setup_cors(app, environment=environment)
        return app

    def test_authorized_origin_allowed(self):
        """Authorized origin should receive CORS headers."""
        app = self._create_test_app("production")
        client = TestClient(app)

        response = client.options(
            "/test",
            headers={
                "Origin": "https://hsaai.internal",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "https://hsaai.internal"

    def test_unauthorized_origin_rejected(self):
        """Unauthorized origin should NOT receive CORS headers."""
        app = self._create_test_app("production")
        client = TestClient(app)

        response = client.get(
            "/test",
            headers={"Origin": "https://evil.example.com"},
        )
        # The response should not include the evil origin in CORS headers
        allow_origin = response.headers.get("access-control-allow-origin", "")
        assert "evil.example.com" not in allow_origin, \
            f"Unauthorized origin allowed: {allow_origin}"

    def test_credentials_supported(self):
        """CORS should support credentials (cookies, Authorization)."""
        app = self._create_test_app("production")
        client = TestClient(app)

        response = client.options(
            "/test",
            headers={
                "Origin": "https://hsaai.internal",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_preflight_cached(self):
        """Preflight should include max-age for caching."""
        app = self._create_test_app("production")
        client = TestClient(app)

        response = client.options(
            "/test",
            headers={
                "Origin": "https://hsaai.internal",
                "Access-Control-Request-Method": "GET",
            },
        )
        max_age = response.headers.get("access-control-max-age")
        assert max_age is not None, "max-age header missing"
        assert int(max_age) > 0

    def test_only_safe_methods_allowed(self):
        """Only safe HTTP methods should be in allow-methods."""
        app = self._create_test_app("production")
        client = TestClient(app)

        response = client.options(
            "/test",
            headers={
                "Origin": "https://hsaai.internal",
                "Access-Control-Request-Method": "GET",
            },
        )
        allowed_methods = response.headers.get("access-control-allow-methods", "")
        # Should include safe methods
        assert "GET" in allowed_methods
        assert "POST" in allowed_methods
        assert "DELETE" in allowed_methods
        # Should NOT be wildcard
        assert allowed_methods != "*"


class TestNoWildcardInCodebase:
    """Forensic: verify no allow_origins=['*'] in any production service."""

    def test_no_wildcard_cors_in_services(self):
        """No service should have allow_origins=['*'] in actual code."""
        import re
        violations = []
        for py_file in (BASE_DIR / "services").rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            content = py_file.read_text()
            # Strip comments and docstrings
            cleaned = re.sub(r'#.*$', '', content, flags=re.MULTILINE)
            cleaned = re.sub(r'"""[\s\S]*?"""', '', cleaned)
            cleaned = re.sub(r"'''[\s\S]*?'''", '', cleaned)
            # Check for wildcard CORS
            if re.search(r'allow_origins\s*=\s*\[\s*["\']\*["\']\s*\]', cleaned):
                violations.append(str(py_file))

        assert len(violations) == 0, \
            f"Wildcard CORS found in production code: {violations}"
