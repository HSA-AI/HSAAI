import importlib
import json
import sys
import types
from urllib.parse import urlparse, parse_qs

import pytest
from fastapi import HTTPException, Response


def _load_auth(monkeypatch):
    # Prevent any real Redis connection attempt during module import.
    if "auth_service.main" not in sys.modules:
        fake_redis = types.ModuleType("redis")
        class RedisFactory:
            @staticmethod
            def from_url(*args, **kwargs):
                class Client:
                    def ping(self):
                        raise RuntimeError("unit-test no redis")
                return Client()
        fake_redis.from_url = RedisFactory.from_url
        monkeypatch.setitem(sys.modules, "redis", fake_redis)
    return importlib.import_module("auth_service.main")


def test_pkce_memory_store_challenge_and_authorize_does_not_leak_verifier(monkeypatch):
    m = _load_auth(monkeypatch)
    monkeypatch.setattr(m, "_redis_client", None)
    m._pkce_states.clear()

    m._pkce_set("s1", {"value": 1})
    assert m._pkce_get("s1") == {"value": 1}
    assert m._pkce_pop("s1") == {"value": 1}
    assert m._pkce_get("s1") is None

    verifier = "A" * 64
    challenge = m.generate_code_challenge(verifier)
    assert challenge
    assert "=" not in challenge

    response = Response()
    payload = m.authorize("http://localhost:3000/api/auth/callback", response)
    assert "code_verifier" not in payload
    assert "authorization_url" in payload
    assert payload["state"] in m._pkce_states

    query = parse_qs(urlparse(payload["authorization_url"]).query)
    assert query["code_challenge_method"] == ["S256"]
    assert query["state"] == [payload["state"]]
    cookie = response.headers.get("set-cookie", "")
    assert "hsaai_pkce_verifier=" in cookie
    assert "HttpOnly" in cookie


@pytest.mark.asyncio
async def test_callback_rejects_invalid_expired_state_and_redirect_mismatch(monkeypatch):
    m = _load_auth(monkeypatch)
    monkeypatch.setattr(m, "_redis_client", None)
    m._pkce_states.clear()

    req = m.TokenExchangeRequest(code="c", state="missing", redirect_uri="http://good")
    with pytest.raises(HTTPException) as exc:
        await m.auth_callback(req, None, Response())
    assert exc.value.status_code == 400

    m._pkce_states["expired"] = {
        "code_verifier": "v",
        "redirect_uri": "http://good",
        "created_at": 0,
    }
    req = m.TokenExchangeRequest(code="c", state="expired", redirect_uri="http://good")
    with pytest.raises(HTTPException) as exc:
        await m.auth_callback(req, None, Response())
    assert exc.value.status_code == 400
    assert "expired" in exc.value.detail.lower()

    m._pkce_states["state2"] = {
        "code_verifier": "v",
        "redirect_uri": "http://good",
        "created_at": m.time.time(),
    }
    req = m.TokenExchangeRequest(code="c", state="state2", redirect_uri="http://evil")
    with pytest.raises(HTTPException) as exc:
        await m.auth_callback(req, None, Response())
    assert exc.value.status_code == 400
    assert "redirect_uri mismatch" in exc.value.detail


def test_current_user_requires_bearer_and_token_verification_fail_closed(monkeypatch):
    m = _load_auth(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        m.current_user(None)
    assert exc.value.status_code == 401

    monkeypatch.setattr(m, "jwt", None)
    with pytest.raises(HTTPException) as exc:
        m.verify_keycloak_token("token")
    assert exc.value.status_code == 500
