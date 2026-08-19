"""
Test: qdrant_client.delete_document_vectors constructs the correct Qdrant
payload filter (must -> document_id -> match -> value).

FIX (HSAAI-DEP-2026-07-11): The function under test is `async def`, but the
original test called it synchronously, producing
`TypeError: 'coroutine' object is not subscriptable` plus a
`coroutine was never awaited` RuntimeWarning. The test now uses an async
dummy client and awaits the coroutine via pytest-asyncio.
"""
import pytest
from backend_core.knowledge import qdrant_client


class DummyResponse:
    status_code = 200
    text = "{}"
    def json(self): return {"status": "ok"}


class DummyAsyncClient:
    """Async-context-manager httpx.AsyncClient stand-in."""
    def __init__(self, *a, **k):
        self.url = None
        self.payload = None
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def post(self, url, json):
        self.url = url
        self.payload = json
        # Sanity-check the filter shape Qdrant expects.
        assert json["filter"]["must"][0]["key"] == "document_id"
        assert json["filter"]["must"][0]["match"]["value"] == "doc_123"
        return DummyResponse()


@pytest.mark.asyncio
async def test_delete_document_vectors_uses_payload_filter(monkeypatch):
    monkeypatch.setattr(qdrant_client.httpx, "AsyncClient", DummyAsyncClient)
    result = await qdrant_client.delete_document_vectors("doc_123")
    assert result["status"] == "ok"
