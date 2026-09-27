import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


def _module():
    import services.rag_engine.main as m
    return m


class FakeRequest:
    def __init__(self, claims=None, path="/v1/test", headers=None):
        self.state = SimpleNamespace(claims=claims or {})
        self.url = SimpleNamespace(path=path)
        self.headers = headers or {}


class FakeUpload:
    def __init__(
        self,
        data=b"enterprise document",
        filename="policy.txt",
        content_type="text/plain",
    ):
        self.data = data
        self.filename = filename
        self.content_type = content_type

    async def read(self, size=-1):
        return self.data


class FakePointStruct:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeQdrantModel:
    def __init__(self, *args, **kwargs):
        self.args = args
        for key, value in kwargs.items():
            setattr(self, key, value)


def _install_qdrant_symbols(monkeypatch, m):
    for name in (
        "Filter",
        "FieldCondition",
        "MatchValue",
        "VectorParams",
    ):
        monkeypatch.setattr(
            m,
            name,
            FakeQdrantModel,
            raising=False,
        )

    monkeypatch.setattr(
        m,
        "PointStruct",
        FakePointStruct,
        raising=False,
    )

    monkeypatch.setattr(
        m,
        "Distance",
        SimpleNamespace(COSINE="cosine"),
        raising=False,
    )


def _install_pii_client(monkeypatch, m, payload, *, status_code=200):
    class Response:
        def __init__(self):
            self.status_code = status_code

        def raise_for_status(self):
            if status_code >= 400:
                raise m.httpx.HTTPStatusError(
                    "PII service error",
                    request=None,
                    response=None,
                )

        def json(self):
            return payload

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


def _configure_upload(
    monkeypatch,
    m,
    tmp_path,
    *,
    pii_payload=None,
    client=None,
    vectors=None,
    chunks=None,
):
    _install_qdrant_symbols(monkeypatch, m)

    monkeypatch.setattr(
        m,
        "verified_scope",
        lambda claims: ("tenant-a", "workspace-a"),
    )

    monkeypatch.setattr(
        m,
        "_event",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        m,
        "outgoing_headers",
        lambda: {},
    )

    monkeypatch.setattr(
        m,
        "STORAGE",
        Path(tmp_path),
    )

    monkeypatch.setenv(
        "USE_OBJECT_STORAGE",
        "false",
    )

    extracted = {
        "text": "enterprise original document",
        "page_map": None,
        "ocr_used": False,
        "extraction_method": "plain_text",
    }

    async def fake_run_in_threadpool(func, *args, **kwargs):
        if func is m.extract_text_with_metadata:
            return dict(extracted)

        return func(*args, **kwargs)

    monkeypatch.setattr(
        m,
        "run_in_threadpool",
        fake_run_in_threadpool,
    )

    if pii_payload is None:
        pii_payload = {
            "decision": "allow",
            "risk_level": "none",
            "pii_types": [],
        }

    _install_pii_client(
        monkeypatch,
        m,
        pii_payload,
    )

    if chunks is None:
        chunks = [
            SimpleNamespace(
                text="enterprise chunk",
                page=1,
                start_char=0,
                end_char=16,
                heading="Policy",
            )
        ]

    monkeypatch.setattr(
        m,
        "chunk_text_advanced",
        lambda *args, **kwargs: chunks,
    )

    if vectors is None:
        vectors = [[0.1, 0.2, 0.3]]

    monkeypatch.setattr(
        m,
        "embed_texts",
        lambda texts: vectors,
        raising=False,
    )

    monkeypatch.setattr(
        m,
        "embed_text",
        lambda text: [0.1, 0.2, 0.3],
    )

    monkeypatch.setattr(
        m,
        "normalize_for_search",
        lambda text: text.lower(),
    )

    monkeypatch.setattr(
        m,
        "embedding_status",
        lambda: {
            "model": "fake-model",
            "vector_size": 3,
        },
    )

    monkeypatch.setattr(
        m,
        "get_qdrant",
        lambda *args, **kwargs: client,
    )


@pytest.mark.asyncio
async def test_protect_api_public_authenticated_and_rejections(monkeypatch):
    m = _module()

    # Public health endpoints bypass authentication.
    public_request = FakeRequest(
        path="/health",
        headers={},
    )

    public_gen = m.protect_api(public_request)

    assert await public_gen.__anext__() is None

    with pytest.raises(StopAsyncIteration):
        await public_gen.__anext__()

    # Missing bearer token.
    missing_request = FakeRequest(
        path="/v1/search",
        headers={},
    )

    missing_gen = m.protect_api(missing_request)

    with pytest.raises(m.HTTPException) as exc:
        await missing_gen.__anext__()

    assert exc.value.status_code == 401

    claims = {
        "sub": "user-a",
        "tenant_id": "tenant-a",
        "workspace_id": "workspace-a",
    }

    async def fake_run_in_threadpool(func, *args, **kwargs):
        return claims

    monkeypatch.setattr(
        m,
        "run_in_threadpool",
        fake_run_in_threadpool,
    )

    monkeypatch.setattr(
        m,
        "verified_scope",
        lambda value: (
            value["tenant_id"],
            value["workspace_id"],
        ),
    )

    authenticated_request = FakeRequest(
        path="/v1/search",
        headers={
            "authorization": "Bearer token-a",
        },
    )

    auth_gen = m.protect_api(authenticated_request)

    assert await auth_gen.__anext__() is None
    assert authenticated_request.state.claims == claims

    await auth_gen.aclose()

    # Invalid verified scope must fail closed.
    def reject_scope(value):
        raise ValueError("invalid tenant scope")

    monkeypatch.setattr(
        m,
        "verified_scope",
        reject_scope,
    )

    denied_request = FakeRequest(
        path="/v1/search",
        headers={
            "authorization": "Bearer token-a",
        },
    )

    denied_gen = m.protect_api(denied_request)

    with pytest.raises(m.HTTPException) as exc:
        await denied_gen.__anext__()

    assert exc.value.status_code == 403


def test_get_qdrant_library_required_create_and_degraded(monkeypatch):
    m = _module()
    _install_qdrant_symbols(monkeypatch, m)

    monkeypatch.setattr(
        m,
        "QdrantClient",
        None,
    )

    monkeypatch.setattr(
        m,
        "REQUIRE_QDRANT",
        False,
    )

    assert m.get_qdrant() is None

    monkeypatch.setattr(
        m,
        "REQUIRE_QDRANT",
        True,
    )

    with pytest.raises(m.HTTPException) as exc:
        m.get_qdrant()

    assert exc.value.status_code == 503

    created = {}

    class Client:
        def __init__(self, *args, **kwargs):
            created["init"] = kwargs

        def get_collections(self):
            return SimpleNamespace(
                collections=[
                    SimpleNamespace(name="other-collection")
                ]
            )

        def create_collection(
            self,
            collection_name,
            vectors_config,
        ):
            created["collection"] = collection_name
            created["size"] = vectors_config.size
            created["distance"] = vectors_config.distance

    monkeypatch.setattr(
        m,
        "QdrantClient",
        Client,
    )

    monkeypatch.setattr(
        m,
        "REQUIRE_QDRANT",
        False,
    )

    client = m.get_qdrant(vector_size=7)

    assert isinstance(client, Client)
    assert created["collection"] == m.COLLECTION
    assert created["size"] == 7
    assert created["distance"] == "cosine"

    class BrokenClient:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("offline")

    monkeypatch.setattr(
        m,
        "QdrantClient",
        BrokenClient,
    )

    assert m.get_qdrant() is None

    monkeypatch.setattr(
        m,
        "REQUIRE_QDRANT",
        True,
    )

    with pytest.raises(m.HTTPException) as exc:
        m.get_qdrant()

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_embed_text_endpoint_success_and_errors(monkeypatch):
    m = _module()

    class Request:
        def __init__(self, payload=None, error=None):
            self.payload = payload
            self.error = error

        async def json(self):
            if self.error:
                raise self.error
            return self.payload

    monkeypatch.setattr(
        m,
        "embed_text",
        lambda text: [0.1, 0.2, 0.3],
    )

    result = await m.embed_text_endpoint(
        Request({"text": "enterprise"})
    )

    assert result["dimensions"] == 3
    assert result["embedding"] == [0.1, 0.2, 0.3]

    with pytest.raises(m.HTTPException) as exc:
        await m.embed_text_endpoint(
            Request(error=ValueError("invalid json"))
        )

    assert exc.value.status_code == 400

    with pytest.raises(m.HTTPException) as exc:
        await m.embed_text_endpoint(
            Request({"text": "   "})
        )

    assert exc.value.status_code == 400

    def broken_embed(text):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(
        m,
        "embed_text",
        broken_embed,
    )

    with pytest.raises(m.HTTPException) as exc:
        await m.embed_text_endpoint(
            Request({"text": "enterprise"})
        )

    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_upload_pii_block_and_invalid_response(
    monkeypatch,
    tmp_path,
):
    m = _module()

    _configure_upload(
        monkeypatch,
        m,
        tmp_path,
        pii_payload={
            "decision": "block",
            "risk_level": "critical",
            "pii_types": ["credit_card"],
        },
    )

    request = FakeRequest(
        claims={
            "tenant_id": "tenant-a",
            "workspace_id": "workspace-a",
        }
    )

    with pytest.raises(m.HTTPException) as exc:
        await m.upload_document(
            request,
            FakeUpload(),
        )

    assert exc.value.status_code == 422

    _install_pii_client(
        monkeypatch,
        m,
        ["not", "a", "dict"],
    )

    with pytest.raises(m.HTTPException) as exc:
        await m.upload_document(
            request,
            FakeUpload(),
        )

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_upload_warn_local_stored_unindexed(
    monkeypatch,
    tmp_path,
):
    m = _module()

    _configure_upload(
        monkeypatch,
        m,
        tmp_path,
        pii_payload={
            "decision": "warn",
            "risk_level": "medium",
            "pii_types": ["email"],
            "redacted_text": "enterprise [REDACTED]",
        },
        client=None,
    )

    monkeypatch.setattr(
        m,
        "REQUIRE_QDRANT",
        False,
    )

    request = FakeRequest(
        claims={
            "tenant_id": "tenant-a",
            "workspace_id": "workspace-a",
        }
    )

    result = await m.upload_document(
        request,
        FakeUpload(),
        visibility="invalid-value",
        allowed_roles="manager, auditor",
        allowed_users="user-1,user-2",
        classification="confidential",
        tags="finance, policy",
    )

    assert result["status"] == "stored_unindexed"
    assert result["tenant_id"] == "tenant-a"
    assert result["workspace_id"] == "workspace-a"
    assert result["persistence"] == "local"

    files = list(Path(tmp_path).rglob("*policy.txt"))

    assert files


@pytest.mark.asyncio
async def test_upload_embedding_incomplete_rejected(
    monkeypatch,
    tmp_path,
):
    m = _module()

    _configure_upload(
        monkeypatch,
        m,
        tmp_path,
        vectors=[],
    )

    request = FakeRequest(
        claims={
            "tenant_id": "tenant-a",
            "workspace_id": "workspace-a",
        }
    )

    with pytest.raises(m.HTTPException) as exc:
        await m.upload_document(
            request,
            FakeUpload(),
        )

    assert exc.value.status_code == 503
    assert "Embedding generation incomplete" in str(
        exc.value.detail
    )


@pytest.mark.asyncio
async def test_upload_rejects_oversized_and_empty_chunks(
    monkeypatch,
    tmp_path,
):
    m = _module()

    _configure_upload(
        monkeypatch,
        m,
        tmp_path,
    )

    monkeypatch.setattr(
        m,
        "MAX_UPLOAD_BYTES",
        4,
    )

    request = FakeRequest(
        claims={
            "tenant_id": "tenant-a",
            "workspace_id": "workspace-a",
        }
    )

    with pytest.raises(m.HTTPException) as exc:
        await m.upload_document(
            request,
            FakeUpload(data=b"12345"),
        )

    assert exc.value.status_code == 413

    monkeypatch.setattr(
        m,
        "MAX_UPLOAD_BYTES",
        1024,
    )

    monkeypatch.setattr(
        m,
        "chunk_text_advanced",
        lambda *args, **kwargs: [],
    )

    with pytest.raises(m.HTTPException) as exc:
        await m.upload_document(
            request,
            FakeUpload(),
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_upload_qdrant_index_success(
    monkeypatch,
    tmp_path,
):
    m = _module()

    class Client:
        def __init__(self):
            self.points = None

        def upsert(
            self,
            collection,
            points,
            wait=True,
        ):
            self.points = points

            return SimpleNamespace(
                status=SimpleNamespace(
                    value="completed",
                )
            )

    client = Client()

    _configure_upload(
        monkeypatch,
        m,
        tmp_path,
        client=client,
    )

    monkeypatch.setattr(
        m,
        "REQUIRE_QDRANT",
        True,
    )

    request = FakeRequest(
        claims={
            "tenant_id": "tenant-a",
            "workspace_id": "workspace-a",
        }
    )

    result = await m.upload_document(
        request,
        FakeUpload(),
        allowed_roles="manager",
        allowed_users="user-a",
        tags="policy,enterprise",
    )

    assert result["status"] == "indexed"
    assert result["persistence"] == "qdrant"
    assert result["chunks"] == 1
    assert result["tags"] == [
        "policy",
        "enterprise",
    ]

    assert len(client.points) == 2
    assert (
        client.points[0].payload["point_type"]
        == "document_metadata"
    )
    assert (
        client.points[1].payload["point_type"]
        == "chunk"
    )


@pytest.mark.asyncio
async def test_upload_qdrant_index_failure(
    monkeypatch,
    tmp_path,
):
    m = _module()

    class Client:
        def upsert(
            self,
            collection,
            points,
            wait=True,
        ):
            return SimpleNamespace(
                status=SimpleNamespace(
                    value="failed",
                )
            )

    _configure_upload(
        monkeypatch,
        m,
        tmp_path,
        client=Client(),
    )

    monkeypatch.setattr(
        m,
        "REQUIRE_QDRANT",
        True,
    )

    request = FakeRequest(
        claims={
            "tenant_id": "tenant-a",
            "workspace_id": "workspace-a",
        }
    )

    with pytest.raises(m.HTTPException) as exc:
        await m.upload_document(
            request,
            FakeUpload(),
            visibility="workspace",
            allowed_roles="",
            allowed_users="",
            classification="internal",
            tags="",
        )

    assert exc.value.status_code == 503
    assert "indexing was not confirmed" in str(
        exc.value.detail
    )


@pytest.mark.asyncio
async def test_upload_object_storage_failure_and_missing_key(
    monkeypatch,
    tmp_path,
):
    m = _module()

    _configure_upload(
        monkeypatch,
        m,
        tmp_path,
        client=None,
    )

    monkeypatch.setattr(
        m,
        "REQUIRE_QDRANT",
        False,
    )

    monkeypatch.setenv(
        "USE_OBJECT_STORAGE",
        "true",
    )

    request = FakeRequest(
        claims={
            "tenant_id": "tenant-a",
            "workspace_id": "workspace-a",
        }
    )

    storage_module = ModuleType(
        "common.storage"
    )

    class BrokenStorage:
        def upload_document(self, **kwargs):
            raise RuntimeError(
                "MinIO unavailable"
            )

    storage_module.storage_client = BrokenStorage()

    monkeypatch.setitem(
        sys.modules,
        "common.storage",
        storage_module,
    )

    with pytest.raises(m.HTTPException) as exc:
        await m.upload_document(
            request,
            FakeUpload(),
        )

    assert exc.value.status_code == 503
    assert "Object storage unavailable" in str(
        exc.value.detail
    )

    class EmptyStorage:
        def upload_document(self, **kwargs):
            return None

    storage_module.storage_client = EmptyStorage()

    with pytest.raises(m.HTTPException) as exc:
        await m.upload_document(
            request,
            FakeUpload(),
        )

    assert exc.value.status_code == 503
    assert "did not confirm upload" in str(
        exc.value.detail
    )
