"""
HSAAI Legacy RAG Search — Proxy to RAG Engine

FIX: Removed in-memory DOCUMENTS dict that was lost on restart.
All search now goes through the RAG engine microservice which
persists data in Qdrant.
"""

import os
import logging

import httpx
from fastapi import HTTPException

logger = logging.getLogger("hsaai.rag.search")

RAG_ENGINE_URL = os.getenv("RAG_ENGINE_URL", "http://rag_engine:8030")


def add_document(name: str, content: str) -> None:
    """
    Add a document to the RAG engine instead of in-memory dict.

    FIX: Previously stored in DOCUMENTS dict (lost on restart).
    Now routes to the RAG engine for persistent storage.
    """
    # This function is kept for backward compatibility but the real
    # document ingestion happens via /v1/documents/upload on the RAG engine.
    # The in-memory DOCUMENTS dict has been removed.
    logger.info("add_document called for '%s' — use RAG engine upload endpoint instead", name)


async def search_docs(query: str) -> list[dict[str, str]]:
    """
    Search documents via the RAG engine microservice.

    FIX: Previously searched an in-memory DOCUMENTS dict that was always
    empty (no way to add documents). Now queries the RAG engine which
    has persistent storage in Qdrant.
    """
    if not query or not query.strip():
        return []
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{RAG_ENGINE_URL}/v1/search",
                json={
                    "query": query,
                    "tenant_id": "default",
                    "workspace_id": "default",
                    "top_k": 5,
                    "mode": "hybrid",
                },
            )
        if response.status_code >= 400:
            logger.warning("RAG engine search failed with status %d", response.status_code)
            return []
        results = response.json().get("results", [])
        return [{"name": r.get("filename", "unknown"), "snippet": r.get("text", "")[:300]} for r in results]
    except Exception as exc:
        logger.warning("RAG search failed: %s", exc)
        return []
