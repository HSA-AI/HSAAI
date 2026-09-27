import importlib.util
import sys
import types
from pathlib import Path

import pytest


MODULE = "_hsaai_rag_proxy_router_test"


class HTTPException(Exception):
    def __init__(self, status_code, detail=None):
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail


class APIRouter:
    def __init__(self, *args, **kwargs):
        pass

    def post(self, *args, **kwargs):
        return lambda func: func

    def delete(self, *args, **kwargs):
        return lambda func: func


def Depends(value=None):
    return value


def File(default=None, **kwargs):
    return default


def Form(default=None, **kwargs):
    return default


class UploadFile:
    pass


class BaseModel:
    pass


class Payload:
    def __init__(self, **kwargs):
        self.values = kwargs

    def model_dump(self):
        return dict(self.values)


class Response:
    def __init__(self, status_code=200, data=None, text=""):
        self.status_code = status_code
        self._data = data or {}
        self.text = text

    def json(self):
        return self._data


class FileObject:
    filename = "test.txt"
    content_type = "text/plain"

    async def read(self):
        return b"document bytes"


def _load():
    existing = sys.modules.get(MODULE)
    if existing is not None:
        return existing

    root = Path(__file__).resolve().parents[2]
    source = root / "services/backend_core/rag/proxy_router.py"

    fastapi = types.ModuleType("fastapi")
    fastapi.APIRouter = APIRouter
    fastapi.UploadFile = UploadFile
    fastapi.File = File
    fastapi.Form = Form
    fastapi.HTTPException = HTTPException
    fastapi.Depends = Depends

    pydantic = types.ModuleType("pydantic")
    pydantic.BaseModel = BaseModel

    auth_pkg = types.ModuleType("common.auth")
    auth_pkg.__path__ = []

    auth = types.ModuleType("common.auth.service_auth")

    async def verify_service_auth():
        return {}

    auth.verify_service_auth = verify_service_auth

    replacements = {
        "fastapi": fastapi,
        "pydantic": pydantic,
        "common.auth": auth_pkg,
        "common.auth.service_auth": auth,
    }

    old = {
        name: sys.modules.get(name)
        for name in replacements
    }

    sys.modules.update(replacements)

    try:
        spec = importlib.util.spec_from_file_location(
            MODULE,
            source,
        )

        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to load {source}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[MODULE] = module
        spec.loader.exec_module(module)

        return module

    finally:
        for name, previous in old.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def _client(monkeypatch, response, captured):
    m = _load()

    class Client:
        def __init__(self, timeout=None):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, **kwargs):
            captured["method"] = "post"
            captured["url"] = url
            captured.update(kwargs)
            return response

        async def delete(self, url, **kwargs):
            captured["method"] = "delete"
            captured["url"] = url
            captured.update(kwargs)
            return response

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        Client,
    )

    return m


CLAIMS = {
    "tenant_id": "tenant-1",
    "workspace_id": "finance",
    "sub": "user-1",
    "roles": ["analyst"],
}


@pytest.mark.asyncio
async def test_upload_success(monkeypatch):
    captured = {}

    m = _client(
        monkeypatch,
        Response(data={"id": "doc-1"}),
        captured,
    )

    result = await m.upload(
        FileObject(),
        visibility="private",
        allowed_roles="analyst",
        allowed_users="user-1",
        classification="confidential",
        tags="finance",
        claims=CLAIMS,
    )

    assert result == {"id": "doc-1"}
    assert captured["timeout"] == 120
    assert captured["data"]["tenant_id"] == "tenant-1"
    assert captured["data"]["workspace_id"] == "finance"
    assert captured["data"]["user_id"] == "user-1"
    assert captured["data"]["user_roles"] == ["analyst"]
    assert captured["files"]["file"][1] == b"document bytes"


@pytest.mark.asyncio
async def test_upload_error(monkeypatch):
    m = _client(
        monkeypatch,
        Response(
            status_code=422,
            text="bad upload",
        ),
        {},
    )

    with pytest.raises(HTTPException) as exc:
        await m.upload(
            FileObject(),
            claims=CLAIMS,
        )

    assert exc.value.status_code == 422
    assert exc.value.detail == "bad upload"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "function_name,path,timeout",
    [
        ("search", "/v1/search", 60),
        ("answer", "/v1/answer", 90),
        ("highlight", "/v1/highlight", 60),
        ("list_documents", "/v1/documents", 60),
        ("analytics", "/v1/analytics", 60),
    ],
)
async def test_json_proxy_successes(
    monkeypatch,
    function_name,
    path,
    timeout,
):
    captured = {}

    m = _client(
        monkeypatch,
        Response(data={"ok": True}),
        captured,
    )

    payload = Payload(
        query="finance",
        top_k=5,
    )

    result = await getattr(
        m,
        function_name,
    )(
        payload,
        CLAIMS,
    )

    assert result == {"ok": True}
    assert captured["timeout"] == timeout
    assert captured["url"].endswith(path)

    body = captured["json"]

    assert body["tenant_id"] == "tenant-1"
    assert body["workspace_id"] == "finance"

    if function_name != "analytics":
        assert body["user_id"] == "user-1"
        assert body["user_roles"] == ["analyst"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "function_name",
    [
        "search",
        "answer",
        "highlight",
        "list_documents",
        "analytics",
    ],
)
async def test_json_proxy_errors(
    monkeypatch,
    function_name,
):
    m = _client(
        monkeypatch,
        Response(
            status_code=503,
            text="rag unavailable",
        ),
        {},
    )

    with pytest.raises(HTTPException) as exc:
        await getattr(
            m,
            function_name,
        )(
            Payload(query="x"),
            CLAIMS,
        )

    assert exc.value.status_code == 503
    assert exc.value.detail == "rag unavailable"


@pytest.mark.asyncio
async def test_delete_success_and_error(monkeypatch):
    captured = {}

    m = _client(
        monkeypatch,
        Response(data={"deleted": True}),
        captured,
    )

    result = await m.delete_document(
        "doc-1",
        CLAIMS,
    )

    assert result == {"deleted": True}
    assert captured["method"] == "delete"

    assert captured["params"] == {
        "tenant_id": "tenant-1",
        "workspace_id": "finance",
    }

    m = _client(
        monkeypatch,
        Response(
            status_code=404,
            text="missing",
        ),
        {},
    )

    with pytest.raises(HTTPException) as exc:
        await m.delete_document(
            "missing",
            CLAIMS,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "missing"
