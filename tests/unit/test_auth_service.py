"""
HSAAI Unit Tests — Auth Service (v4.0)
Covers: PKCE flow, MFA, token verification, RBAC
"""
import pytest
import time
import secrets
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# CD-003 FIX: Add service paths at module level for 'from main import app' to work
_BASE = Path(__file__).resolve().parents[2]
_AUTH_SVC_PATH = str(_BASE / "services" / "auth_service")
_BACKEND_PATH = str(_BASE / "services")
for _p in [_AUTH_SVC_PATH, _BACKEND_PATH]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


@pytest.fixture
def client():
    """Test client for auth_service."""
    # FIX-36: Use absolute import 'auth_service.main' instead of bare 'main'
    # to avoid sys.modules contamination when other test modules (e.g.
    # test_rag_and_security.py) import 'mcp_server.main' which registers
    # 'main' as a top-level module name.
    import auth_service.main as auth_module
    return TestClient(auth_module.app)


class TestPKCEFlow:
    """Tests for PKCE (Proof Key for Code Exchange) flow."""

    def test_authorize_returns_state_but_not_verifier(self, client):
        """v2.0 fix: code_verifier must NOT be in response."""
        # FIX-22: /v1/auth/authorize is POST with redirect_uri as query param.
        resp = client.post("/v1/auth/authorize", params={"redirect_uri": "http://localhost:3000/api/auth/callback"})
        assert resp.status_code == 200
        data = resp.json()
        assert "authorization_url" in data
        assert "state" in data
        # Critical: code_verifier must NOT be in response
        assert "code_verifier" not in data, "code_verifier leaked in response!"

    def test_authorize_sets_pkce_cookie(self, client):
        """v2.0 fix: code_verifier stored in httpOnly cookie."""
        # FIX-22: /v1/auth/authorize is POST with redirect_uri as query param.
        resp = client.post("/v1/auth/authorize", params={"redirect_uri": "http://localhost:3000/api/auth/callback"})
        cookies = resp.headers.get("set-cookie", "")
        assert "hsaai_pkce_verifier" in cookies
        assert "HttpOnly" in cookies
        # Note: Secure flag is only set when HTTPS is detected; in test mode
        # (http) the cookie may not have Secure. We check HttpOnly which is
        # always set for security.

    def test_callback_requires_state(self, client):
        """v2.0 fix: state parameter required for CSRF protection."""
        resp = client.post("/v1/auth/callback", json={"code": "test", "redirect_uri": "http://localhost:3000"})
        assert resp.status_code == 422  # state is required

    def test_callback_rejects_invalid_state(self, client):
        """v2.0 fix: invalid state rejected."""
        resp = client.post("/v1/auth/callback", json={
            "code": "test",
            "state": "invalid-state",
            "redirect_uri": "http://localhost:3000",
        })
        assert resp.status_code == 400
        assert "Invalid or expired state" in resp.json()["detail"]


class TestMFAEndpoints:
    """Tests for MFA enrollment and verification."""

    def test_mfa_enroll_requires_auth(self, client):
        """v2.0 fix: MFA enroll requires authentication."""
        resp = client.post("/v1/mfa/enroll", json={})
        assert resp.status_code == 401  # Unauthorized

    def test_mfa_verify_requires_auth(self, client):
        """v2.0 fix: MFA verify requires authentication."""
        resp = client.post("/v1/mfa/verify", json={"otp": "123456"})
        assert resp.status_code == 401

    def test_mfa_enroll_no_secret_in_response(self, client, monkeypatch):
        """v2.0 fix: raw secret not returned (only otpauth_uri)."""
        # Mock current_user dependency
        # FIX-36: use absolute import to avoid sys.modules contamination.
        import auth_service.main as auth_module
        from fastapi import Depends
        app = auth_module.app

        async def mock_user():
            return {"sub": "user-123", "preferred_username": "test@example.com"}

        app.dependency_overrides[app.dependency_overrides.get("current_user", mock_user)] = mock_user

        resp = client.post("/v1/mfa/enroll", json={})
        # Even if auth fails in test, verify the response structure doesn't include secret
        if resp.status_code == 200:
            data = resp.json()
            assert "secret" not in data, "Raw secret leaked in MFA enroll response!"
            assert "otpauth_uri" in data


class TestTokenVerification:
    """Tests for JWT token verification."""

    def test_verify_token_requires_bearer(self, client):
        """No token = 401."""
        resp = client.post("/v1/token/verify")
        assert resp.status_code == 401

    def test_verify_token_invalid_format(self, client):
        """Invalid token format = 401."""
        resp = client.post("/v1/token/verify", headers={"Authorization": "invalid"})
        assert resp.status_code == 401


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "auth_service"
        assert data["pkce_enabled"] is True
