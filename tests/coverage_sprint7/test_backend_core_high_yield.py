import importlib
from types import SimpleNamespace

import pytest


def _module():
    # Termux test environment does not necessarily include prometheus_client.
    # GitHub/production uses the real package.  Only install this lightweight
    # in-process stub when the dependency is genuinely unavailable.
    import sys
    import types

    try:
        importlib.import_module("prometheus_client")
    except ModuleNotFoundError:
        prometheus = types.ModuleType("prometheus_client")

        class _Metric:
            def __init__(self, *args, **kwargs):
                pass

            def labels(self, *args, **kwargs):
                return self

            def inc(self, *args, **kwargs):
                return None

            def observe(self, *args, **kwargs):
                return None

            def set(self, *args, **kwargs):
                return None

            def time(self):
                class _Timer:
                    def __enter__(self):
                        return self

                    def __exit__(self, exc_type, exc, tb):
                        return False

                return _Timer()

        prometheus.Counter = _Metric
        prometheus.Histogram = _Metric
        prometheus.Gauge = _Metric
        prometheus.generate_latest = lambda *args, **kwargs: b""
        prometheus.CONTENT_TYPE_LATEST = (
            "text/plain; version=0.0.4; charset=utf-8"
        )

        sys.modules["prometheus_client"] = prometheus

    return importlib.import_module("services.backend_core.main")


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

    async def read(self):
        return self.data


def _settings(
    *,
    allowed="application/pdf,text/plain",
    max_bytes=1024,
    graph=False,
):
    return SimpleNamespace(
        allowed_upload_mime_types=allowed,
        max_upload_bytes=max_bytes,
        knowledge_graph_enabled=graph,
        graph_ingestion_enabled=graph,
    )


@pytest.mark.asyncio
async def test_startup_development_initializes_db_and_qdrant(monkeypatch):
    m = _module()
    calls = []

    monkeypatch.setenv("APP_ENV", "development")

    monkeypatch.setattr(
        m,
        "setup_logging",
        lambda **kwargs: calls.append(
            ("logging", kwargs)
        ),
        raising=False,
    )

    monkeypatch.setattr(
        m,
        "init_sentry",
        lambda: calls.append(("sentry", None)),
        raising=False,
    )

    monkeypatch.setattr(
        m,
        "init_db",
        lambda: calls.append(("init_db", None)),
    )

    async def ensure():
        calls.append(("qdrant", None))

    monkeypatch.setattr(
        m,
        "ensure_collection",
        ensure,
    )

    await m.startup()

    assert ("init_db", None) in calls
    assert ("qdrant", None) in calls


@pytest.mark.asyncio
async def test_startup_qdrant_failure_is_nonfatal(monkeypatch):
    m = _module()

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setattr(m, "setup_logging", None, raising=False)
    monkeypatch.setattr(m, "init_sentry", None, raising=False)
    monkeypatch.setattr(m, "init_db", lambda: None)

    async def broken():
        raise RuntimeError("qdrant offline")

    monkeypatch.setattr(
        m,
        "ensure_collection",
        broken,
    )

    # Development startup deliberately survives Qdrant outage.
    await m.startup()


@pytest.mark.asyncio
async def test_startup_production_runs_migrations(monkeypatch):
    m = _module()

    dbmod = importlib.import_module(
        "backend_core.db.database"
    )

    calls = []

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(m, "setup_logging", None, raising=False)
    monkeypatch.setattr(m, "init_sentry", None, raising=False)

    monkeypatch.setattr(
        m,
        "init_db",
        lambda: calls.append("init_db"),
    )

    monkeypatch.setattr(
        dbmod,
        "run_migrations",
        lambda: calls.append("migrations"),
    )

    async def ensure():
        calls.append("qdrant")

    monkeypatch.setattr(
        m,
        "ensure_collection",
        ensure,
    )

    await m.startup()

    assert "migrations" in calls
    assert "qdrant" in calls
    assert "init_db" not in calls


@pytest.mark.asyncio
async def test_startup_production_migration_failure_is_fatal(
    monkeypatch,
):
    m = _module()

    dbmod = importlib.import_module(
        "backend_core.db.database"
    )

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(m, "setup_logging", None, raising=False)
    monkeypatch.setattr(m, "init_sentry", None, raising=False)

    def broken_migrations():
        raise RuntimeError("migration failed")

    monkeypatch.setattr(
        dbmod,
        "run_migrations",
        broken_migrations,
    )

    with pytest.raises(
        RuntimeError,
        match="migration failed",
    ):
        await m.startup()


@pytest.mark.asyncio
async def test_upload_file_rejects_mime_size_and_executable(
    monkeypatch,
):
    m = _module()

    monkeypatch.setattr(
        m,
        "settings",
        _settings(max_bytes=4),
    )

    with pytest.raises(m.HTTPException) as exc:
        await m.upload_file(
            FakeUpload(
                data=b"x",
                content_type="application/x-msdownload",
            )
        )

    assert exc.value.status_code == 415

    with pytest.raises(m.HTTPException) as exc:
        await m.upload_file(
            FakeUpload(
                data=b"12345",
                content_type="application/pdf",
            )
        )

    assert exc.value.status_code == 413

    monkeypatch.setattr(
        m,
        "settings",
        _settings(max_bytes=1024),
    )

    with pytest.raises(m.HTTPException) as exc:
        await m.upload_file(
            FakeUpload(
                data=b"echo hello",
                filename="payload.sh",
                content_type="text/plain",
            )
        )

    assert exc.value.status_code == 415
    assert "Executable" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_upload_file_rag_http_failure(monkeypatch):
    m = _module()

    monkeypatch.setattr(
        m,
        "settings",
        _settings(),
    )

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            raise m.httpx.HTTPError("rag offline")

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        Client,
    )

    with pytest.raises(m.HTTPException) as exc:
        await m.upload_file(
            FakeUpload()
        )

    assert exc.value.status_code == 502
    assert "RAG Engine unavailable" in str(
        exc.value.detail
    )


@pytest.mark.asyncio
async def test_upload_file_propagates_rag_error(monkeypatch):
    m = _module()

    monkeypatch.setattr(
        m,
        "settings",
        _settings(),
    )

    class Response:
        status_code = 422
        text = "document rejected by rag"

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
        await m.upload_file(
            FakeUpload()
        )

    assert exc.value.status_code == 422
    assert "document rejected" in str(
        exc.value.detail
    )


@pytest.mark.asyncio
async def test_upload_file_success_without_graph(monkeypatch):
    m = _module()

    monkeypatch.setattr(
        m,
        "settings",
        _settings(graph=False),
    )

    captured = {}

    class Response:
        status_code = 200

        def json(self):
            return {
                "document_id": "doc-1",
                "status": "indexed",
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
            captured["kwargs"] = kwargs
            return Response()

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        Client,
    )

    result = await m.upload_file(
        FakeUpload(),
        tenant_id="tenant-a",
        workspace_id="workspace-a",
    )

    assert result["document_id"] == "doc-1"
    assert (
        result["routed_by"]
        == "backend_core:/files/upload"
    )
    assert (
        result["canonical_endpoint"]
        == "/v1/rag/documents/upload"
    )

    assert captured["kwargs"]["data"] == {
        "tenant_id": "tenant-a",
        "workspace_id": "workspace-a",
    }


@pytest.mark.asyncio
async def test_upload_file_graph_ingestion_success(monkeypatch):
    m = _module()

    monkeypatch.setattr(
        m,
        "settings",
        _settings(graph=True),
    )

    class Response:
        status_code = 200

        def json(self):
            return {
                "document_id": "doc-graph",
                "summary": "Enterprise summary",
                "classification": "internal",
                "permissions": ["reader"],
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

    state = {
        "closed": False,
        "ingested": None,
    }

    class DB:
        def close(self):
            state["closed"] = True

    monkeypatch.setattr(
        m,
        "SessionLocal",
        lambda: DB(),
        raising=False,
    )

    class Graph:
        def __init__(self, db):
            self.db = db

        def ingest_document(
            self,
            document,
            **kwargs,
        ):
            state["ingested"] = {
                "document": document,
                "kwargs": kwargs,
            }

    monkeypatch.setattr(
        m,
        "GraphService",
        Graph,
        raising=False,
    )

    result = await m.upload_file(
        FakeUpload(filename="graph.pdf"),
        tenant_id="tenant-a",
        workspace_id="workspace-a",
    )

    assert result["knowledge_graph_ingested"] is True
    assert state["closed"] is True
    assert (
        state["ingested"]["document"]["document_id"]
        == "doc-graph"
    )
    assert (
        state["ingested"]["kwargs"]["tenant_id"]
        == "tenant-a"
    )


@pytest.mark.asyncio
async def test_upload_file_graph_failure_is_reported(monkeypatch):
    m = _module()

    monkeypatch.setattr(
        m,
        "settings",
        _settings(graph=True),
    )

    class Response:
        status_code = 200

        def json(self):
            return {
                "id": "doc-2",
                "status": "indexed",
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

    state = {"closed": False}

    class DB:
        def close(self):
            state["closed"] = True

    monkeypatch.setattr(
        m,
        "SessionLocal",
        lambda: DB(),
        raising=False,
    )

    class BrokenGraph:
        def __init__(self, db):
            pass

        def ingest_document(self, *args, **kwargs):
            raise RuntimeError(
                "knowledge graph unavailable"
            )

    monkeypatch.setattr(
        m,
        "GraphService",
        BrokenGraph,
        raising=False,
    )

    result = await m.upload_file(
        FakeUpload(),
    )

    assert result["knowledge_graph_ingested"] is False
    assert "knowledge graph unavailable" in result[
        "knowledge_graph_error"
    ]
    assert state["closed"] is True
