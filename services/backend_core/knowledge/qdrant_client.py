import os
from typing import Any

import httpx
from backend_core.config import settings

QDRANT_URL = settings.qdrant_url
QDRANT_COLLECTION = settings.qdrant_collection
QDRANT_API_KEY = settings.qdrant_api_key


def _delete_payload(document_id: str) -> dict[str, Any]:
    return {"filter": {"must": [{"key": "document_id", "match": {"value": document_id}}]}}


def _delete_url() -> str:
    return f"{QDRANT_URL.rstrip('/')}/collections/{QDRANT_COLLECTION}/points/delete?wait=true"

class QdrantDeleteError(RuntimeError):
    pass

def _headers() -> dict[str, str]:
    return {"api-key": QDRANT_API_KEY} if QDRANT_API_KEY else {}

async def qdrant_health() -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=5, headers=_headers()) as client:
            r = await client.get(f"{QDRANT_URL.rstrip('/')}/collections/{QDRANT_COLLECTION}")
            if r.status_code == 404:
                return {"status": "missing_collection", "collection": QDRANT_COLLECTION}
            r.raise_for_status()
            return {"status": "ok", "collection": QDRANT_COLLECTION}
    except Exception as exc:
        return {"status": "error", "error": str(exc)[:300]}

async def ensure_collection() -> dict[str, Any]:
    url = f"{QDRANT_URL.rstrip('/')}/collections/{QDRANT_COLLECTION}"
    payload = {"vectors": {"size": settings.qdrant_vector_size, "distance": "Cosine"}}
    try:
        async with httpx.AsyncClient(timeout=20, headers=_headers()) as client:
            current = await client.get(url)
            if current.status_code == 200:
                return {"status": "exists", "collection": QDRANT_COLLECTION}
            response = await client.put(url, json=payload)
            response.raise_for_status()
            return {"status": "created", "collection": QDRANT_COLLECTION, "vector_size": settings.qdrant_vector_size}
    except Exception as exc:
        if settings.require_qdrant and settings.is_production:
            raise RuntimeError(f"Qdrant collection is required in production: {exc}") from exc
        return {"status": "error", "error": str(exc)[:300]}

async def delete_document_vectors_async(document_id: str) -> dict[str, Any]:
    """Async variant — for callers already inside an event loop."""
    payload = _delete_payload(document_id)
    url = _delete_url()
    try:
        async with httpx.AsyncClient(timeout=30, headers=_headers()) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        raise QdrantDeleteError(f"Qdrant delete request failed: {type(exc).__name__}") from exc
    if response.status_code >= 400:
        raise QdrantDeleteError(f"Qdrant delete failed: HTTP {response.status_code}")
    return response.json()


def delete_document_vectors(document_id: str) -> dict[str, Any]:
    """BLOCKING sync variant.

    FIXED (audit — real bug caught by tests/backend/test_qdrant_delete_sync.py):
    this used to be `async def` while its only callers
    (KnowledgeHubService.archive_document / .delete_document) are SYNC methods
    that invoked it WITHOUT await. Calling a coroutine without awaiting
    executes NOTHING: the Qdrant delete request was never sent, vectors were
    orphaned after every archive/delete, and QdrantDeleteError could never be
    raised (the error-handling paths were dead code). The calling routes are
    sync FastAPI handlers (threadpool), so a blocking httpx.Client call is
    safe here.
    """
    payload = _delete_payload(document_id)
    url = _delete_url()
    try:
        with httpx.Client(timeout=30, headers=_headers()) as client:
            response = client.post(url, json=payload)
    except httpx.HTTPError as exc:
        raise QdrantDeleteError(f"Qdrant delete request failed: {type(exc).__name__}") from exc
    if response.status_code >= 400:
        raise QdrantDeleteError(f"Qdrant delete failed: HTTP {response.status_code}")
    return response.json()
