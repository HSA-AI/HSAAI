import json
from types import SimpleNamespace

import pytest


def _module():
    import services.api_gateway.main as m
    return m


class FakeUpload:
    def __init__(
        self,
        data=b"enterprise document",
        filename="policy.pdf",
        content_type="application/pdf",
    ):
        self.data = data
        self.filename = filename
        self.content_type = content_type

    async def read(self, size=-1):
        return self.data


class FakeRequest:
    def __init__(self, headers=None):
        self.headers = headers or {}


def test_assert_internal_only_config_success(monkeypatch):
    m = _module()

    monkeypatch.setattr(m, "INTERNAL_ONLY_MODE", True)
    monkeypatch.setattr(m, "ALLOW_EXTERNAL_APIS", False)
    monkeypatch.setattr(m, "STRICT_EGRESS_DENY", True)

    for key in m.BLOCKED_EXTERNAL_SECRET_KEYS:
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setattr(
        m,
        "_is_private_url",
        lambda url: True,
    )

    result = m.assert_internal_only_config()

    assert result["internal_only_mode"] is True
    assert result["allow_external_apis"] is False
    assert result["strict_egress_deny"] is True
    assert result["blocked_keys_present"] == []


def test_assert_internal_only_config_rejects_external_secret(monkeypatch):
    m = _module()

    monkeypatch.setattr(m, "INTERNAL_ONLY_MODE", True)
    monkeypatch.setattr(m, "ALLOW_EXTERNAL_APIS", False)
    monkeypatch.setattr(m, "STRICT_EGRESS_DENY", True)
    monkeypatch.setattr(
        m,
        "_is_private_url",
        lambda url: True,
    )

    for key in m.BLOCKED_EXTERNAL_SECRET_KEYS:
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "forbidden-test-secret",
    )

    with pytest.raises(RuntimeError) as exc:
        m.assert_internal_only_config()

    assert "External AI/API secrets are forbidden" in str(exc.value)


def test_assert_internal_only_config_rejects_external_upstream(monkeypatch):
    m = _module()

    monkeypatch.setattr(m, "INTERNAL_ONLY_MODE", True)
    monkeypatch.setattr(m, "ALLOW_EXTERNAL_APIS", False)
    monkeypatch.setattr(m, "STRICT_EGRESS_DENY", True)

    for key in m.BLOCKED_EXTERNAL_SECRET_KEYS:
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv(
        "RAG_ENGINE_URL",
        "https://public.example.com",
    )

    monkeypatch.setattr(
        m,
        "_is_private_url",
        lambda url: "public.example.com" not in url,
    )

    with pytest.raises(RuntimeError) as exc:
        m.assert_internal_only_config()

    assert "External upstream URLs are forbidden" in str(exc.value)


def test_guard_upstream_url_allow_and_block(monkeypatch):
    m = _module()

    monkeypatch.setattr(m, "INTERNAL_ONLY_MODE", True)
    monkeypatch.setattr(m, "ALLOW_EXTERNAL_APIS", False)
    monkeypatch.setattr(m, "STRICT_EGRESS_DENY", True)

    monkeypatch.setattr(
        m,
        "_is_private_url",
        lambda url: url.startswith("http://rag_engine"),
    )

    # Internal URL is allowed.
    m.guard_upstream_url(
        "http://rag_engine:8030/v1/search"
    )

    # Public URL is blocked.
    with pytest.raises(m.HTTPException) as exc:
        m.guard_upstream_url(
            "https://public.example.com/api"
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_upload_rag_document_success_claim_scope(monkeypatch):
    m = _module()

    captured = {}

    monkeypatch.setattr(
        m,
        "guard_upstream_url",
        lambda url: captured.setdefault("guarded_url", url),
    )

    monkeypatch.setattr(
        m,
        "forward_headers",
        lambda request, claims=None: {
            "Authorization": "Bearer forwarded"
        },
    )

    class Response:
        status_code = 201

        def json(self):
            return {
                "status": "indexed",
                "doc_id": "doc-123",
            }

    class Client:
        def __init__(self, *args, **kwargs):
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, **kwargs):
            captured["url"] = url
            captured["post"] = kwargs
            return Response()

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        Client,
    )

    monkeypatch.setenv(
        "RAG_MAX_UPLOAD_BYTES",
        "1024",
    )

    response = await m.upload_rag_document(
        FakeRequest(),
        FakeUpload(
            data=b"document-data",
            filename="enterprise.pdf",
        ),
        tenant_id="client-tenant",
        workspace_id="client-workspace",
        claims={
            "tenant_id": "trusted-tenant",
            "workspace_id": "trusted-workspace",
        },
    )

    assert response.status_code == 201

    body = json.loads(response.body)
    assert body["status"] == "indexed"
    assert body["doc_id"] == "doc-123"

    assert captured["guarded_url"].endswith(
        "/v1/documents/upload"
    )
    assert captured["url"].endswith(
        "/v1/documents/upload"
    )

    post = captured["post"]

    # Authenticated claims must override client-supplied form scope.
    assert post["data"]["tenant_id"] == "trusted-tenant"
    assert (
        post["data"]["workspace_id"]
        == "trusted-workspace"
    )

    assert (
        post["files"]["file"][0]
        == "enterprise.pdf"
    )
    assert (
        post["files"]["file"][1]
        == b"document-data"
    )
    assert (
        post["headers"]["Authorization"]
        == "Bearer forwarded"
    )


@pytest.mark.asyncio
async def test_upload_rag_document_falls_back_to_form_scope(monkeypatch):
    m = _module()

    captured = {}

    monkeypatch.setattr(
        m,
        "guard_upstream_url",
        lambda url: None,
    )

    monkeypatch.setattr(
        m,
        "forward_headers",
        lambda request, claims=None: {},
    )

    class Response:
        status_code = 200

        def json(self):
            return {"status": "ok"}

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, **kwargs):
            captured.update(kwargs)
            return Response()

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        Client,
    )

    monkeypatch.setenv(
        "RAG_MAX_UPLOAD_BYTES",
        "1024",
    )

    response = await m.upload_rag_document(
        FakeRequest(),
        FakeUpload(),
        tenant_id="form-tenant",
        workspace_id="form-workspace",
        claims={},
    )

    assert response.status_code == 200
    assert captured["data"]["tenant_id"] == "form-tenant"
    assert (
        captured["data"]["workspace_id"]
        == "form-workspace"
    )


@pytest.mark.asyncio
async def test_upload_rag_document_size_limit(monkeypatch):
    m = _module()

    monkeypatch.setenv(
        "RAG_MAX_UPLOAD_BYTES",
        "4",
    )

    with pytest.raises(m.HTTPException) as exc:
        await m.upload_rag_document(
            FakeRequest(),
            FakeUpload(data=b"12345"),
            tenant_id="tenant-a",
            workspace_id="workspace-a",
            claims={
                "tenant_id": "tenant-a",
                "workspace_id": "workspace-a",
            },
        )

    assert exc.value.status_code == 413
    assert "configured limit" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_upload_rag_document_invalid_json_response(monkeypatch):
    m = _module()

    monkeypatch.setenv(
        "RAG_MAX_UPLOAD_BYTES",
        "1024",
    )

    monkeypatch.setattr(
        m,
        "guard_upstream_url",
        lambda url: None,
    )

    monkeypatch.setattr(
        m,
        "forward_headers",
        lambda request, claims=None: {},
    )

    class Response:
        status_code = 502

        def json(self):
            raise ValueError("not json")

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        Client,
    )

    with pytest.raises(m.HTTPException) as exc:
        await m.upload_rag_document(
            FakeRequest(),
            FakeUpload(),
            tenant_id="tenant-a",
            workspace_id="workspace-a",
            claims={
                "tenant_id": "tenant-a",
                "workspace_id": "workspace-a",
            },
        )

    assert exc.value.status_code == 502
    assert "invalid JSON" in str(exc.value.detail)


class GatewayRequest:
    def __init__(
        self,
        *,
        path="/v1/protected",
        headers=None,
        cookies=None,
        method="POST",
        body=b"",
        client_host="127.0.0.1",
    ):
        self.url = SimpleNamespace(path=path)
        self.headers = headers or {}
        self.cookies = cookies or {}
        self.method = method
        self._body = body
        self.client = (
            SimpleNamespace(host=client_host)
            if client_host is not None
            else None
        )

    async def body(self):
        return self._body


@pytest.mark.asyncio
async def test_enforce_rate_limit_allow_and_reject(monkeypatch):
    m = _module()

    class Limiter:
        def __init__(self):
            self.allowed = True
            self.keys = []

        def allow(self, key):
            self.keys.append(key)
            return self.allowed

    limiter = Limiter()
    monkeypatch.setattr(m, "_limiter", limiter)

    req = GatewayRequest(client_host="10.0.0.8")

    await m.enforce_rate_limit(req)

    assert limiter.keys[-1] == "10.0.0.8"

    limiter.allowed = False

    with pytest.raises(m.HTTPException) as exc:
        await m.enforce_rate_limit(req)

    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"] == "60"

    # No client information uses the safe fallback key.
    limiter.allowed = True

    await m.enforce_rate_limit(
        GatewayRequest(client_host=None)
    )

    assert limiter.keys[-1] == "unknown"


@pytest.mark.asyncio
async def test_verify_session_public_and_missing_token(monkeypatch):
    m = _module()

    async def no_rate_limit(request):
        return None

    monkeypatch.setattr(
        m,
        "enforce_rate_limit",
        no_rate_limit,
    )

    public = GatewayRequest(
        path="/health",
    )

    claims = await m.verify_session(public)

    assert claims["active"] is True
    assert claims["sub"] == "anonymous"
    assert claims["tenant_id"] == "default"

    protected = GatewayRequest(
        path="/v1/protected",
    )

    with pytest.raises(m.HTTPException) as exc:
        await m.verify_session(protected)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Missing bearer token"


@pytest.mark.asyncio
async def test_verify_session_cookie_token_success(monkeypatch):
    m = _module()

    async def no_rate_limit(request):
        return None

    monkeypatch.setattr(
        m,
        "enforce_rate_limit",
        no_rate_limit,
    )

    captured = {}

    claims = {
        "sub": "user-a",
        "roles": ["employee"],
        "tenant_id": "tenant-a",
        "workspace_id": "workspace-a",
    }

    class Response:
        status_code = 200

        def json(self):
            return claims

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, **kwargs):
            captured["url"] = url
            captured["headers"] = kwargs["headers"]
            return Response()

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        Client,
    )

    monkeypatch.setattr(
        m,
        "verified_scope",
        lambda value: (
            value["tenant_id"],
            value["workspace_id"],
        ),
    )

    request = GatewayRequest(
        cookies={
            "hsaai_access_token": "cookie-token",
        }
    )

    result = await m.verify_session(request)

    assert result == claims
    assert captured["url"].endswith(
        "/v1/token/verify"
    )
    assert (
        captured["headers"]["Authorization"]
        == "Bearer cookie-token"
    )


@pytest.mark.asyncio
async def test_verify_session_rejects_invalid_auth_response(monkeypatch):
    m = _module()

    async def no_rate_limit(request):
        return None

    monkeypatch.setattr(
        m,
        "enforce_rate_limit",
        no_rate_limit,
    )

    class Response:
        status_code = 401

        def json(self):
            return {}

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        Client,
    )

    request = GatewayRequest(
        headers={
            "authorization": "Bearer invalid",
        }
    )

    with pytest.raises(m.HTTPException) as exc:
        await m.verify_session(request)

    assert exc.value.status_code == 401
    assert "Invalid or expired" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_verify_session_auth_service_and_scope_failures(monkeypatch):
    m = _module()

    async def no_rate_limit(request):
        return None

    monkeypatch.setattr(
        m,
        "enforce_rate_limit",
        no_rate_limit,
    )

    request = GatewayRequest(
        headers={
            "authorization": "Bearer token-a",
        }
    )

    class BrokenClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            raise m.httpx.HTTPError(
                "auth service offline"
            )

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        BrokenClient,
    )

    with pytest.raises(m.HTTPException) as exc:
        await m.verify_session(request)

    assert exc.value.status_code == 503

    class Response:
        status_code = 200

        def json(self):
            return {
                "sub": "user-a",
                "tenant_id": "bad-tenant",
            }

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        Client,
    )

    def reject_scope(claims):
        raise ValueError("tenant scope invalid")

    monkeypatch.setattr(
        m,
        "verified_scope",
        reject_scope,
    )

    with pytest.raises(m.HTTPException) as exc:
        await m.verify_session(request)

    assert exc.value.status_code == 403
    assert "tenant scope invalid" in str(
        exc.value.detail
    )


@pytest.mark.asyncio
async def test_forward_auth_request_preserves_body_headers_and_cookies(
    monkeypatch,
):
    m = _module()

    async def no_rate_limit(request):
        return None

    monkeypatch.setattr(
        m,
        "enforce_rate_limit",
        no_rate_limit,
    )

    captured = {}

    class UpstreamHeaders:
        def get(self, key, default=None):
            if key.lower() == "content-type":
                return "application/json"
            return default

        def get_list(self, key):
            if key.lower() == "set-cookie":
                return [
                    "hsaai_access_token=abc; HttpOnly; Path=/",
                    "hsaai_refresh_token=xyz; HttpOnly; Path=/",
                ]
            return []

    class Upstream:
        status_code = 200
        content = b'{"ok":true}'
        headers = UpstreamHeaders()

    class Client:
        def __init__(self, *args, **kwargs):
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(
            self,
            method,
            url,
            **kwargs,
        ):
            captured["method"] = method
            captured["url"] = url
            captured["kwargs"] = kwargs
            return Upstream()

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        Client,
    )

    request = GatewayRequest(
        method="POST",
        body=b'{"code":"abc"}',
        headers={
            "authorization": "Bearer token-a",
            "content-type": "application/json",
            "cookie": "session=1",
            "x-requested-with": "XMLHttpRequest",
            "origin": "http://localhost:3000",
            "x-should-not-forward": "secret",
        },
    )

    response = await m._forward_auth_request(
        request,
        "/v1/auth/callback",
    )

    assert response.status_code == 200
    assert response.body == b'{"ok":true}'

    assert captured["method"] == "POST"
    assert captured["url"].endswith(
        "/v1/auth/callback"
    )
    assert (
        captured["kwargs"]["content"]
        == b'{"code":"abc"}'
    )

    forwarded = captured["kwargs"]["headers"]

    assert forwarded["authorization"] == "Bearer token-a"
    assert forwarded["content-type"] == "application/json"
    assert forwarded["cookie"] == "session=1"
    assert "x-should-not-forward" not in forwarded

    cookie_headers = [
        value.decode()
        for key, value in response.raw_headers
        if key.lower() == b"set-cookie"
    ]

    assert len(cookie_headers) == 2
    assert any(
        "hsaai_access_token=abc" in value
        for value in cookie_headers
    )
    assert any(
        "hsaai_refresh_token=xyz" in value
        for value in cookie_headers
    )


@pytest.mark.asyncio
async def test_forward_auth_request_upstream_failure(monkeypatch):
    m = _module()

    async def no_rate_limit(request):
        return None

    monkeypatch.setattr(
        m,
        "enforce_rate_limit",
        no_rate_limit,
    )

    class BrokenClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, *args, **kwargs):
            raise m.httpx.HTTPError(
                "auth upstream offline"
            )

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        BrokenClient,
    )

    request = GatewayRequest(
        method="GET",
        body=b"",
        headers={},
    )

    with pytest.raises(m.HTTPException) as exc:
        await m._forward_auth_request(
            request,
            "/v1/keycloak/config",
        )

    assert exc.value.status_code == 503
    assert exc.value.detail == "Auth service unavailable"
