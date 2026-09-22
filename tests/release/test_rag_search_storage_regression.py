
"""Focused search and storage regressions for HSAAI RAG."""

import ast
from pathlib import Path

from rag_engine import main, reranker


def function_node(name):
    source = Path(main.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    matches = [
        node for node in tree.body
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        )
        and node.name == name
    ]

    assert len(matches) == 1
    return matches[0]


def test_search_event_never_records_raw_query():
    node = function_node("search")

    events = [
        call for call in ast.walk(node)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "_event"
        and call.args
        and isinstance(call.args[0], ast.Constant)
        and call.args[0].value == "search"
    ]

    assert len(events) == 1

    keyword_names = {
        keyword.arg for keyword in events[0].keywords
    }

    assert "query" not in keyword_names


def test_upload_records_original_storage_reference():
    node = function_node("upload_document")

    string_values = {
        n.value for n in ast.walk(node)
        if isinstance(n, ast.Constant)
        and isinstance(n.value, str)
    }

    assert "storage_backend" in string_values
    assert "storage_key" in string_values


def test_qdrant_upsert_waits_for_completion():
    node = function_node("upload_document")

    upserts = [
        n for n in ast.walk(node)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "upsert"
    ]

    assert len(upserts) == 1

    wait = [
        keyword.value
        for keyword in upserts[0].keywords
        if keyword.arg == "wait"
    ]

    assert len(wait) == 1
    assert isinstance(wait[0], ast.Constant)
    assert wait[0].value is True


def test_hybrid_reranker_returns_ranked_candidates():
    hits = [
        {"score": 0.9, "text": "invoice payment approved"},
        {"score": 0.5, "text": "network infrastructure"},
    ]

    result = reranker.rerank(
        "invoice payment",
        hits,
        use_cross_encoder=False,
        use_mmr=False,
    )

    assert len(result) == 2
    assert all("rerank_score" in item for item in result)

    scores = [item["rerank_score"] for item in result]
    assert scores == sorted(scores, reverse=True)


def test_mmr_reuses_tokenized_documents(monkeypatch):
    original = reranker.tokenize
    calls = []

    def counted(text):
        calls.append(text)
        return original(text)

    monkeypatch.setattr(reranker, "tokenize", counted)

    candidates = [
        {"rerank_score": 0.9, "text": "invoice payment"},
        {"rerank_score": 0.8, "text": "invoice approved"},
        {"rerank_score": 0.7, "text": "network infrastructure"},
    ]

    result = reranker._mmr_rerank(
        candidates,
        top_k=3,
    )

    assert len(result) == 3

    # Each unique candidate should be tokenized at most once
    # during the MMR similarity comparisons.
    assert len(calls) <= len({
        item["text"] for item in candidates
    })
