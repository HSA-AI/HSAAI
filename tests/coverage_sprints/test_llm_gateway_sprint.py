import importlib
import json

import pytest
from fastapi import HTTPException


def _module():
    return importlib.import_module("llm_gateway.main")


def test_cache_key_semantic_cache_and_token_budget(monkeypatch):
    m = _module()
    a = m._cache_key("p", "s", "model", 0.2, 100)
    b = m._cache_key("p", "s", "model", 0.2, 101)
    assert a != b
    assert a == m._cache_key("p", "s", "model", 0.2, 100)

    class Redis:
        stored = {}
        def get(self, key):
            return self.stored.get(key)
        def setex(self, key, ttl, value):
            self.stored[key] = value

    redis = Redis()
    monkeypatch.setattr(m, "ENABLE_SEMANTIC_CACHE", True)
    monkeypatch.setattr(m, "_get_redis_client", lambda url: redis)
    assert m._check_semantic_cache("p", "s", "model", 0.2, "tenant") is None
    m._store_in_semantic_cache("p", "s", "model", 0.2, "tenant", {"text": "cached"}, ttl=60)
    assert m._check_semantic_cache("p", "s", "model", 0.2, "tenant")["text"] == "cached"

    monkeypatch.setattr(m, "ENABLE_TOKEN_BUDGET", True)
    class BudgetRedis:
        def get(self, key):
            return "90" if key.startswith("token_budget:") and "limit" not in key else ("100" if "limit" in key else None)
    monkeypatch.setattr(m, "_get_redis_client", lambda url: BudgetRedis())
    allowed, used, budget = m._check_token_budget("tenant", 20)
    assert allowed is False
    assert used == 90
    assert budget == 100


def test_token_budget_fail_closed_in_production(monkeypatch):
    m = _module()
    monkeypatch.setattr(m, "ENABLE_TOKEN_BUDGET", True)
    monkeypatch.setattr(m, "_get_redis_client", lambda url: None)
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(HTTPException) as exc:
        m._check_token_budget("tenant", 100)
    assert exc.value.status_code == 503


def test_external_ai_security_guards(monkeypatch):
    m = _module()
    monkeypatch.setattr(m, "LOCAL_ONLY", True)
    monkeypatch.setattr(m, "ALLOW_EXTERNAL_AI", True)
    with pytest.raises(HTTPException) as exc:
        m.assert_no_external_ai()
    assert exc.value.status_code == 500

    monkeypatch.setattr(m, "ALLOW_EXTERNAL_AI", False)
    for key in m.BLOCKED_EXTERNAL_SECRET_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "should-never-exist-in-local-mode")
    with pytest.raises(HTTPException) as exc:
        m.assert_no_external_ai()
    assert "secrets are forbidden" in exc.value.detail

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(m, "STRICT_EGRESS_DENY", True)
    monkeypatch.setattr(m, "OLLAMA_BASE_URL", "https://public.example.com")
    monkeypatch.setattr(m, "_is_private_url", lambda url: False)
    with pytest.raises(HTTPException) as exc:
        m.assert_no_external_ai()
    assert "company network" in exc.value.detail


@pytest.mark.asyncio
async def test_generate_budget_rejection_and_cache_hit(monkeypatch):
    m = _module()
    req = m.GenerateRequest(prompt="hello", max_tokens=10, tenant_id="body", workspace_id="body")
    claims = {"tenant_id": "t1", "workspace_id": "w1", "sub": "u1"}

    import common.security.request_policy as rp
    monkeypatch.setattr(rp, "verified_scope", lambda claims: ("t1", "w1"))
    monkeypatch.setattr(m, "assert_no_external_ai", lambda: None)
    monkeypatch.setattr(
        m, "route_model",
        lambda *args, **kwargs: {"model": "qwen", "provider": "ollama", "local_only": True, "reason": "test"},
    )
    monkeypatch.setattr(m, "_estimate_tokens", lambda text: 5)
    monkeypatch.setattr(m, "_check_token_budget", lambda *args: (False, 99, 100))
    with pytest.raises(HTTPException) as exc:
        await m.generate(req, claims)
    assert exc.value.status_code == 429

    monkeypatch.setattr(m, "_check_token_budget", lambda *args: (True, 0, 1000))
    monkeypatch.setattr(
        m, "_check_semantic_cache",
        lambda *args, **kwargs: {"text": "cached answer", "provider": "cache"},
    )
    result = await m.generate(req, claims)
    assert result.text == "cached answer"
    assert "semantic_cache_hit" in result.route_reason
    assert result.model == "qwen"
