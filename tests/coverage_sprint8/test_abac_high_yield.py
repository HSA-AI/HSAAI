import time

import pytest
from fastapi import HTTPException


def _m():
    import common.abac as module
    return module


@pytest.fixture(autouse=True)
def clear_abac_cache():
    m = _m()
    m._decision_cache.clear()
    yield
    m._decision_cache.clear()


def test_cache_key_explicit_and_fallback_resource():
    m = _m()

    user = {
        "sub": "user-1",
        "tenant_id": "tenant-1",
    }

    explicit = m._cache_key(
        user,
        "documents:read",
        {
            "id": "doc-1",
            "type": "document",
        },
    )

    assert explicit == (
        "user-1",
        "tenant-1",
        "documents:read",
        "doc-1",
    )

    fallback = m._cache_key(
        {},
        "read",
        {
            "b": 2,
            "a": 1,
        },
    )

    assert fallback[0] == "unknown"
    assert fallback[1] == "default"
    assert fallback[2] == "read"
    assert "a" in fallback[3]


def test_cache_hit_expiry_and_set_eviction(
    monkeypatch,
):
    m = _m()

    monkeypatch.setattr(
        m.time,
        "time",
        lambda: 1000.0,
    )

    live = ("u", "t", "read", "1")
    expired = ("u", "t", "read", "2")

    m._decision_cache[live] = (
        True,
        1100.0,
    )

    m._decision_cache[expired] = (
        False,
        900.0,
    )

    assert m._get_cached(live) is True
    assert m._get_cached(expired) is None
    assert expired not in m._decision_cache

    old = ("old", "t", "read", "x")

    m._decision_cache[old] = (
        True,
        999.0,
    )

    new = ("new", "t", "read", "y")

    m._set_cached(
        new,
        False,
    )

    assert old not in m._decision_cache
    assert new in m._decision_cache
    assert (
        m._decision_cache[new][0]
        is False
    )


@pytest.mark.asyncio
async def test_abac_disabled_allows():
    m = _m()

    old = m.ABAC_ENABLED

    try:
        m.ABAC_ENABLED = False

        result = await m.check_access(
            {"sub": "u"},
            "documents:delete",
            {"id": "d1"},
        )

        assert result is True

    finally:
        m.ABAC_ENABLED = old


@pytest.mark.asyncio
async def test_cached_decision_short_circuits(
    monkeypatch,
):
    m = _m()

    monkeypatch.setattr(
        m,
        "ABAC_ENABLED",
        True,
    )

    user = {
        "sub": "u1",
        "tenant_id": "t1",
    }

    resource = {
        "id": "doc-1",
    }

    key = m._cache_key(
        user,
        "documents:read",
        resource,
    )

    m._decision_cache[key] = (
        True,
        time.time() + 100,
    )

    class MustNotRun:
        def __init__(self, *args, **kwargs):
            raise AssertionError(
                "HTTP client should not run"
            )

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        MustNotRun,
    )

    assert (
        await m.check_access(
            user,
            "documents:read",
            resource,
        )
        is True
    )


@pytest.mark.asyncio
async def test_opa_success_and_cache(
    monkeypatch,
):
    m = _m()

    monkeypatch.setattr(
        m,
        "ABAC_ENABLED",
        True,
    )

    captured = {}

    class Response:
        status_code = 200

        def json(self):
            return {"result": True}

    class Client:
        def __init__(self, timeout=None):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(
            self,
            exc_type,
            exc,
            tb,
        ):
            return False

        async def post(
            self,
            url,
            json=None,
        ):
            captured["url"] = url
            captured["json"] = json
            return Response()

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        Client,
    )

    user = {
        "sub": "user-1",
        "roles": ["employee"],
        "tenant_id": "tenant-1",
        "workspace_id": "finance",
        "department": "finance",
        "clearance": "confidential",
        "mfa_verified": True,
    }

    resource = {
        "id": "doc-1",
        "type": "document",
        "tenant_id": "tenant-1",
        "classification": "internal",
        "owner": "user-1",
    }

    result = await m.check_access(
        user,
        "documents:read",
        resource,
        {
            "ip": "10.0.0.1",
            "time": "12:00",
            "device": "managed",
        },
    )

    assert result is True
    assert captured["timeout"] == m.OPA_TIMEOUT

    assert captured["url"].endswith(
        "/v1/data/hsaai/abac/allow"
    )

    payload = captured["json"]["input"]

    assert payload["user"]["sub"] == "user-1"
    assert payload["resource"]["id"] == "doc-1"
    assert payload["env"]["device"] == "managed"

    key = m._cache_key(
        user,
        "documents:read",
        resource,
    )

    assert m._decision_cache[key][0] is True


@pytest.mark.asyncio
async def test_opa_success_false_result(
    monkeypatch,
):
    m = _m()

    monkeypatch.setattr(
        m,
        "ABAC_ENABLED",
        True,
    )

    class Response:
        status_code = 200

        def json(self):
            return {"result": False}

    class Client:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(
            self,
            exc_type,
            exc,
            tb,
        ):
            return False

        async def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        Client,
    )

    assert (
        await m.check_access(
            {"sub": "u"},
            "write",
            {"id": "r"},
        )
        is False
    )


@pytest.mark.asyncio
async def test_opa_http_status_fail_closed(
    monkeypatch,
):
    m = _m()

    monkeypatch.setattr(
        m,
        "ABAC_ENABLED",
        True,
    )
    monkeypatch.setenv(
        "ABAC_FAIL_OPEN",
        "false",
    )

    class Response:
        status_code = 503

    class Client:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(
            self,
            exc_type,
            exc,
            tb,
        ):
            return False

        async def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        Client,
    )

    result = await m.check_access(
        {"sub": "u"},
        "documents:delete",
        {"id": "d"},
    )

    assert result is False


@pytest.mark.asyncio
async def test_opa_http_status_explicit_fail_open(
    monkeypatch,
):
    m = _m()

    monkeypatch.setattr(
        m,
        "ABAC_ENABLED",
        True,
    )
    monkeypatch.setenv(
        "ABAC_FAIL_OPEN",
        "true",
    )

    class Response:
        status_code = 500

    class Client:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(
            self,
            exc_type,
            exc,
            tb,
        ):
            return False

        async def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        Client,
    )

    assert (
        await m.check_access(
            {"sub": "u"},
            "write",
            {"id": "x"},
        )
        is True
    )


@pytest.mark.asyncio
async def test_http_error_fail_closed_and_open(
    monkeypatch,
):
    m = _m()

    monkeypatch.setattr(
        m,
        "ABAC_ENABLED",
        True,
    )

    class Client:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(
            self,
            exc_type,
            exc,
            tb,
        ):
            return False

        async def post(self, *args, **kwargs):
            raise m.httpx.ConnectError(
                "OPA unavailable"
            )

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        Client,
    )

    monkeypatch.setenv(
        "ABAC_FAIL_OPEN",
        "false",
    )

    assert (
        await m.check_access(
            {"sub": "u"},
            "read",
            {"id": "r1"},
        )
        is False
    )

    monkeypatch.setenv(
        "ABAC_FAIL_OPEN",
        "true",
    )

    assert (
        await m.check_access(
            {"sub": "u2"},
            "read",
            {"id": "r2"},
        )
        is True
    )


@pytest.mark.asyncio
async def test_generic_error_fail_closed_and_open(
    monkeypatch,
):
    m = _m()

    monkeypatch.setattr(
        m,
        "ABAC_ENABLED",
        True,
    )

    class Client:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            raise RuntimeError(
                "unexpected failure"
            )

        async def __aexit__(
            self,
            exc_type,
            exc,
            tb,
        ):
            return False

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        Client,
    )

    monkeypatch.setenv(
        "ABAC_FAIL_OPEN",
        "false",
    )

    assert (
        await m.check_access(
            {"sub": "u"},
            "write",
            {"id": "1"},
        )
        is False
    )

    monkeypatch.setenv(
        "ABAC_FAIL_OPEN",
        "true",
    )

    assert (
        await m.check_access(
            {"sub": "u2"},
            "write",
            {"id": "2"},
        )
        is True
    )


@pytest.mark.asyncio
async def test_check_access_or_raise_allow(
    monkeypatch,
):
    m = _m()

    async def allow(*args, **kwargs):
        return True

    monkeypatch.setattr(
        m,
        "check_access",
        allow,
    )

    assert (
        await m.check_access_or_raise(
            {"sub": "u"},
            "read",
            {"type": "document"},
        )
        is None
    )


@pytest.mark.asyncio
async def test_check_access_or_raise_denied_with_id(
    monkeypatch,
):
    m = _m()

    async def deny(*args, **kwargs):
        return False

    monkeypatch.setattr(
        m,
        "check_access",
        deny,
    )

    with pytest.raises(
        HTTPException,
    ) as exc:
        await m.check_access_or_raise(
            {"sub": "u"},
            "documents:delete",
            {
                "type": "document",
                "id": "doc-9",
            },
        )

    assert exc.value.status_code == 403
    assert "document doc-9" in str(
        exc.value.detail
    )


@pytest.mark.asyncio
async def test_decision_reason_disabled(
    monkeypatch,
):
    m = _m()

    monkeypatch.setattr(
        m,
        "ABAC_ENABLED",
        False,
    )

    assert (
        await m.get_decision_reason(
            {},
            "read",
            {},
        )
        == "abac_disabled"
    )


@pytest.mark.asyncio
async def test_decision_reason_success(
    monkeypatch,
):
    m = _m()

    monkeypatch.setattr(
        m,
        "ABAC_ENABLED",
        True,
    )

    captured = {}

    class Response:
        status_code = 200

        def json(self):
            return {
                "result": {
                    "reason":
                        "insufficient_clearance"
                }
            }

    class Client:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(
            self,
            exc_type,
            exc,
            tb,
        ):
            return False

        async def post(
            self,
            url,
            json=None,
        ):
            captured["url"] = url
            captured["json"] = json
            return Response()

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        Client,
    )

    reason = await m.get_decision_reason(
        {"sub": "u"},
        "read",
        {"id": "doc"},
        {"ip": "127.0.0.1"},
    )

    assert reason == "insufficient_clearance"
    assert captured["url"].endswith(
        "/v1/data/hsaai/abac/decision"
    )


@pytest.mark.asyncio
async def test_decision_reason_unknown_paths(
    monkeypatch,
):
    m = _m()

    monkeypatch.setattr(
        m,
        "ABAC_ENABLED",
        True,
    )

    class BadStatus:
        status_code = 500

    class StatusClient:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(
            self,
            exc_type,
            exc,
            tb,
        ):
            return False

        async def post(self, *args, **kwargs):
            return BadStatus()

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        StatusClient,
    )

    assert (
        await m.get_decision_reason(
            {},
            "read",
            {},
        )
        == "unknown"
    )

    class ErrorClient:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            raise RuntimeError("boom")

        async def __aexit__(
            self,
            exc_type,
            exc,
            tb,
        ):
            return False

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        ErrorClient,
    )

    assert (
        await m.get_decision_reason(
            {},
            "read",
            {},
        )
        == "unknown"
    )
