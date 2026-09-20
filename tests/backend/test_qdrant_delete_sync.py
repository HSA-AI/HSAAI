from backend_core.knowledge import qdrant_client

class DummyResponse:
    status_code = 200
    text = "{}"
    def json(self): return {"status": "ok"}

class DummyClient:
    def __init__(self, *a, **k): self.url = None; self.payload = None
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def post(self, url, json):
        self.url = url
        self.payload = json
        assert json["filter"]["must"][0]["key"] == "document_id"
        assert json["filter"]["must"][0]["match"]["value"] == "doc_123"
        return DummyResponse()

def test_delete_document_vectors_uses_payload_filter(monkeypatch):
    monkeypatch.setattr(qdrant_client.httpx, "Client", DummyClient)
    assert qdrant_client.delete_document_vectors("doc_123")["status"] == "ok"
