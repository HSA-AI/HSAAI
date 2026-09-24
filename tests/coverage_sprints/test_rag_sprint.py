import importlib
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException


def _main():
    return importlib.import_module("rag_engine.main")


def _loaders():
    return importlib.import_module("rag_engine.loaders")


class Upload:
    def __init__(self, data: bytes, filename="a.txt", content_type="text/plain"):
        self.data = data
        self.filename = filename
        self.content_type = content_type

    async def read(self, n=-1):
        return self.data if n < 0 else self.data[:n]


class PiiResp:
    def __init__(self, data, status=200):
        self.data = data
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "http://pii-detector")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("bad", request=request, response=response)

    def json(self):
        return self.data


class PiiClient:
    response = PiiResp({"decision": "allow", "risk_level": "none"})

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, *args, **kwargs):
        if isinstance(type(self).response, Exception):
            raise type(self).response
        return type(self).response


def _request():
    return SimpleNamespace(state=SimpleNamespace(claims={"tenant_id": "t1", "workspace_id": "w1"}))


def _patch_upload_dependencies(monkeypatch, m, tmp_path, pii=None, qdrant=True, vectors=True):
    monkeypatch.setenv("USE_OBJECT_STORAGE", "false")
    monkeypatch.setattr(m, "STORAGE", tmp_path / "storage")
    monkeypatch.setattr(m, "verified_scope", lambda claims: ("t1", "w1"))
    monkeypatch.setattr(m.httpx, "AsyncClient", PiiClient)
    if pii is not None:
        PiiClient.response = pii
    else:
        PiiClient.response = PiiResp({"decision": "allow", "risk_level": "none"})

    async def run_in_threadpool(fn, *args, **kwargs):
        return {"text": "enterprise policy text", "page_map": [], "ocr_used": False, "extraction_method": "plain-text"}
    monkeypatch.setattr(m, "run_in_threadpool", run_in_threadpool)

    chunk = SimpleNamespace(
        text="enterprise policy text", page=1, start_char=0, end_char=22, heading="Policy"
    )
    monkeypatch.setattr(m, "chunk_text_advanced", lambda *args, **kwargs: [chunk])
    monkeypatch.setattr(m, "embed_texts", lambda texts: [[0.1, 0.2]] if vectors else [], raising=False)
    monkeypatch.setattr(m, "normalize_for_search", lambda text: text.lower())
    monkeypatch.setattr(m, "PointStruct", lambda **kwargs: kwargs)
    monkeypatch.setattr(m, "_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(m, "embedding_status", lambda: {"backend": "mock"})

    class Client:
        def upsert(self, *args, **kwargs):
            return SimpleNamespace(status=SimpleNamespace(value="completed"))

    monkeypatch.setattr(m, "get_qdrant", lambda *args, **kwargs: Client() if qdrant else None)


def test_loader_plain_text_and_image_ocr(monkeypatch):
    m = _loaders()
    plain = m.extract_text_with_metadata("a.txt", b"hello")
    assert plain["text"] == "hello"
    assert plain["extraction_method"] == "plain-text"

    monkeypatch.setattr(m, "_try_ocr_image", lambda raw: "OCR TEXT")
    image = m.extract_text_with_metadata("scan.png", b"fake-image", enable_ocr=True)
    assert image["text"] == "OCR TEXT"
    assert image["ocr_used"] is True
    assert image["extraction_method"] == "ocr-image-tesseract"


@pytest.mark.asyncio
async def test_upload_rejects_oversize_before_external_calls(monkeypatch):
    m = _main()
    monkeypatch.setattr(m, "MAX_UPLOAD_BYTES", 4)
    monkeypatch.setattr(m, "verified_scope", lambda claims: ("t1", "w1"))
    with pytest.raises(HTTPException) as exc:
        await m.upload_document(_request(), Upload(b"12345"))
    assert exc.value.status_code == 413


@pytest.mark.asyncio
async def test_upload_pii_fail_closed_paths(monkeypatch, tmp_path):
    m = _main()

    _patch_upload_dependencies(
        monkeypatch, m, tmp_path,
        pii=PiiResp({"decision": "block", "risk_level": "critical", "pii_types": ["national_id"]}),
    )
    with pytest.raises(HTTPException) as exc:
        await m.upload_document(_request(), Upload(b"safe bytes"))
    assert exc.value.status_code == 422

    _patch_upload_dependencies(
        monkeypatch, m, tmp_path,
        pii=PiiResp({"decision": "allow", "risk_level": "high"}),
    )
    with pytest.raises(HTTPException) as exc:
        await m.upload_document(_request(), Upload(b"safe bytes"))
    assert exc.value.status_code == 503

    request = httpx.Request("POST", "http://pii-detector")
    _patch_upload_dependencies(
        monkeypatch, m, tmp_path,
        pii=httpx.ConnectError("down", request=request),
    )
    with pytest.raises(HTTPException) as exc:
        await m.upload_document(_request(), Upload(b"safe bytes"))
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_upload_happy_path_uses_mock_qdrant_and_local_storage(monkeypatch, tmp_path):
    m = _main()
    monkeypatch.setattr(m, "MAX_UPLOAD_BYTES", 10_000_000)
    _patch_upload_dependencies(monkeypatch, m, tmp_path, qdrant=True, vectors=True)

    result = await m.upload_document(
        _request(),
        Upload(b"enterprise policy"),
        visibility="restricted",
        allowed_roles="admin,auditor",
        allowed_users="u1",
        classification="confidential",
        tags="hr,policy",
    )
    assert result["status"] == "indexed"
    assert result["tenant_id"] == "t1"
    assert result["workspace_id"] == "w1"
    assert result["classification"] == "confidential"
    assert result["tags"] == ["hr", "policy"]
    assert result["acl"]["allowed_roles"] == ["admin", "auditor"]


@pytest.mark.asyncio
async def test_upload_rejects_incomplete_embeddings_and_qdrant_outage(monkeypatch, tmp_path):
    m = _main()
    monkeypatch.setattr(m, "MAX_UPLOAD_BYTES", 10_000_000)

    _patch_upload_dependencies(monkeypatch, m, tmp_path, vectors=False)
    with pytest.raises(HTTPException) as exc:
        await m.upload_document(_request(), Upload(b"enterprise policy"))
    assert exc.value.status_code == 503
    assert "Embedding" in exc.value.detail

    _patch_upload_dependencies(monkeypatch, m, tmp_path, qdrant=False, vectors=True)
    monkeypatch.setattr(m, "REQUIRE_QDRANT", True)
    with pytest.raises(HTTPException) as exc:
        await m.upload_document(_request(), Upload(b"enterprise policy"))
    assert exc.value.status_code == 503
    assert "Qdrant" in exc.value.detail


def test_search_fail_closed_without_tenant_or_qdrant(monkeypatch):
    m = _main()
    req = m.SearchRequest(query="policy", tenant_id="body-tenant", workspace_id="body-ws", top_k=3, mode="hybrid")
    monkeypatch.setattr(m, "_scope_request", lambda req, claims: req)

    with pytest.raises(HTTPException) as exc:
        m.search(req, {})
    assert exc.value.status_code == 403

    monkeypatch.setattr(m, "embed_text", lambda q: [0.1, 0.2])
    monkeypatch.setattr(m, "get_qdrant", lambda *args: None)
    monkeypatch.setattr(m, "REQUIRE_QDRANT", True)
    with pytest.raises(HTTPException) as exc:
        m.search(req, {"tenant_id": "claim-tenant", "workspace_id": "claim-ws"})
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_answer_no_sources_and_llm_fallback(monkeypatch):
    m = _main()
    req = m.AnswerRequest(query="What is policy?", tenant_id="t1", workspace_id="w1")
    monkeypatch.setattr(m, "_scope_request", lambda req, claims: req)
    monkeypatch.setattr(m, "_event", lambda *args, **kwargs: None)

    async def no_hits(fn, *args, **kwargs):
        return {"results": []}
    monkeypatch.setattr(m, "run_in_threadpool", no_hits)
    result = await m.answer(req, {"tenant_id": "t1"})
    assert result["answer_type"] == "no_sources"
    assert result["sources"] == []

    hits = [{
        "doc_id": "d1", "filename": "policy.pdf", "page": 1,
        "chunk_index": 0, "text": "Annual leave is thirty days.",
        "score": 0.9, "start_char": 0, "end_char": 28,
    }]
    async def with_hits(fn, *args, **kwargs):
        return {"results": hits}
    monkeypatch.setattr(m, "run_in_threadpool", with_hits)
    monkeypatch.setattr(m, "RAG_ANSWER_USE_LLM", False)
    result = await m.answer(req, {"tenant_id": "t1"})
    assert result["answer_type"] == "retrieval_fallback"
    assert result["sources"][0]["doc_id"] == "d1"
    assert "Annual leave" in result["answer"]
