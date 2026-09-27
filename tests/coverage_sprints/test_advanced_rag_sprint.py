import importlib
import time

import pytest


def _module():
    return importlib.import_module("common.ai.advanced_rag")


class Resp:
    def __init__(self, status=200, data=None):
        self.status_code = status
        self._data = data or {}

    def json(self):
        return self._data


class QueueClient:
    def __init__(self, items):
        self.items = list(items)
        self.calls = []
        self.closed = False

    async def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def aclose(self):
        self.closed = True


def test_auto_mode_selection_and_parameterized_graph_query():
    m = _module()
    e = m.AdvancedRAGEngine()
    assert e._select_mode("relationship overview") == m.RetrievalMode.GRAPH
    assert e._select_mode("latest news") == m.RetrievalMode.CORRECTIVE
    assert e._select_mode("show chart image") == m.RetrievalMode.MULTIMODAL
    assert e._select_mode("ordinary policy question") == m.RetrievalMode.HYBRID

    query = e._build_graph_query(["Acme"], "t' OR 1=1", 9999)
    assert "$tenant" in query
    assert "$names" in query
    assert "t' OR 1=1" not in query


@pytest.mark.asyncio
async def test_graph_rag_happy_path_uses_parameters():
    m = _module()
    e = m.AdvancedRAGEngine()
    e.client = QueueClient([
        Resp(200, {"text": '["Policy","HR"]'}),
        Resp(200, {"results": [{"name": "Policy"}]}),
        Resp(200, {"results": [{"text": "doc", "score": 0.91}]}),
    ])

    result = await e._graph_rag("policy relationships", "tenant-A", 5, time.time())
    assert result.mode == "graph"
    assert result.graph_entities[0]["name"] == "Policy"
    assert result.documents[0]["score"] == 0.91
    graph_call = e.client.calls[1]
    assert graph_call[2]["json"]["params"]["tenant"] == "tenant-A"
    assert graph_call[2]["json"]["params"]["names"] == ["Policy", "HR"]


@pytest.mark.asyncio
async def test_self_rag_can_skip_retrieval_and_defaults_to_retrieve_on_error():
    m = _module()
    e = m.AdvancedRAGEngine()
    e.client = QueueClient([Resp(200, {"text": "NO"})])
    result = await e._self_rag("2+2?", "t", 5, time.time())
    assert result.documents == []
    assert result.sources_used == ["model_knowledge"]

    e.client = QueueClient([
        RuntimeError("llm down"),
        Resp(200, {"results": [{"content": "relevant policy"}]}),
        Resp(200, {"text": "0.9"}),
    ])
    result = await e._self_rag("policy?", "t", 5, time.time())
    assert len(result.documents) == 1
    assert result.documents[0]["relevance_score"] == 0.9


@pytest.mark.asyncio
async def test_multimodal_real_embedding_and_metadata_fallback():
    m = _module()
    e = m.AdvancedRAGEngine()

    e.client = QueueClient([
        Resp(200, {"results": [{"type": "text", "text": "doc"}]}),
        Resp(200, {"embedding": [0.1, 0.2]}),
        Resp(200, {"result": [{
            "score": 0.88,
            "payload": {"image_url": "img://1", "caption": "budget chart", "source_document": "budget.pdf"},
        }]}),
    ])
    real = await e._multimodal_rag("budget chart", "t", 5, time.time())
    assert real.embedding_source == "real"
    assert any(d.get("embedding_source") == "real" for d in real.documents if isinstance(d, dict))

    e.client = QueueClient([
        Resp(200, {"results": []}),
        RuntimeError("embed down"),
        Resp(200, {"result": {"points": [
            {"payload": {"image_url": "img://2", "caption": "budget chart", "source_document": "x.pdf"}},
            {"payload": {"image_url": "img://3", "caption": "unrelated", "source_document": "y.pdf"}},
        ]}}),
    ])
    fallback = await e._multimodal_rag("budget chart", "t", 5, time.time())
    assert fallback.embedding_source == "metadata_fallback"
    assert fallback.documents[0]["url"] == "img://2"
