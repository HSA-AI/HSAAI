import time
import pytest

class Resp:
    def __init__(self, data=None, status_code=200, exc=None):
        self._data = data or {}
        self.status_code = status_code
        self.exc = exc
    def raise_for_status(self):
        if self.exc:
            raise self.exc
    def json(self):
        return self._data

class Client:
    def __init__(self, gets=None, posts=None):
        self.gets = list(gets or [])
        self.posts = list(posts or [])
    async def get(self, *args, **kwargs):
        item = self.gets.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
    async def post(self, *args, **kwargs):
        item = self.posts.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_circuit_breaker_transitions(monkeypatch):
    import common.security.vault_client as v

    cb = v.CircuitBreakerState(threshold=2, reset_timeout=5)
    assert cb.can_attempt() is True
    cb.record_failure()
    assert cb.state == "closed"
    cb.record_failure()
    assert cb.state == "open"
    assert cb.can_attempt() is False

    monkeypatch.setattr(v.time, "time", lambda: cb.last_failure + 10)
    assert cb.can_attempt() is True
    assert cb.state == "half-open"
    cb.record_success()
    assert cb.state == "closed" and cb.failure_count == 0


@pytest.mark.asyncio
async def test_vault_read_cache_write_health_and_fallback(monkeypatch):
    import common.security.vault_client as v

    c = v.VaultClient()
    c._initialized = True
    c.token = "token"
    c.namespace = "ns"
    c._client = Client(
        gets=[
            Resp({"data": {"data": {"password": "secret"}}, "lease_duration": 60, "lease_id": "l1"}),
            Resp({"sealed": False}, 200),
            RuntimeError("health down"),
        ],
        posts=[Resp({})],
    )

    secret = await c.read_secret("secret/data/db", cache_ttl=30)
    assert secret["password"] == "secret"
    assert c._cb.state == "closed"

    cached = await c.read_secret("secret/data/db", cache_ttl=30)
    assert cached == secret
    assert c.get_audit_log()[-1]["action"] == "cache_hit"

    assert await c.write_secret("secret/data/db", {"password": "rotated"}) is True
    assert "secret/data/db" not in c._cache

    c._cache["a"] = v.CacheEntry({"x": 1}, time.time() + 30)
    c.invalidate_cache("a")
    assert "a" not in c._cache
    c._cache["b"] = v.CacheEntry({"x": 1}, time.time() + 30)
    c.invalidate_cache()
    assert c._cache == {}

    healthy = await c.health_check()
    assert healthy["healthy"] is True and healthy["sealed"] is False
    unhealthy = await c.health_check()
    assert unhealthy["healthy"] is False

    async def fail_read(path):
        raise v.CircuitBreakerOpen("open")
    monkeypatch.setattr(c, "read_secret", fail_read)
    monkeypatch.setenv("API_KEY", "env-value")
    assert await c.get_secret_value("x", "api-key", "d") == "env-value"


@pytest.mark.asyncio
async def test_vault_approle_and_renew_success_and_failure():
    import common.security.vault_client as v

    c = v.VaultClient()
    c._client = Client(posts=[
        Resp({"auth": {"client_token": "abc", "lease_duration": 60}}),
        Resp({"auth": {"lease_duration": 120}}),
        RuntimeError("renew failed"),
    ])

    await c._auth_approle("r", "s")
    assert c.token == "abc"
    assert c._token_expires_at > 0

    await c._renew_token()
    with pytest.raises(RuntimeError):
        await c._renew_token()


def test_vault_initialize_fail_closed_and_dev(monkeypatch):
    import common.security.vault_client as v

    for key in ("VAULT_TOKEN", "VAULT_APPROLE_ROLE_ID", "VAULT_APPROLE_SECRET_ID", "VAULT_K8S_ROLE"):
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("DEPLOY_ENV", "production")
    c = v.VaultClient()
    with pytest.raises(SystemExit):
        c.initialize()

    monkeypatch.setenv("DEPLOY_ENV", "development")
    c2 = v.VaultClient()
    c2.initialize()
    assert c2._initialized is True
    assert c2.token == ""
