import os
from typing import Any

import httpx
from backend_core.config import settings

QDRANT_URL = settings.qdrant_url
QDRANT_COLLECTION = settings.qdrant_collection
QDRANT_API_KEY = settings.qdrant_api_key

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

async def delete_document_vectors(document_id: str) -> dict[str, Any]:
    payload = {"filter": {"must": [{"key": "document_id", "match": {"value": document_id}}]}}
    url = f"{QDRANT_URL.rstrip('/')}/collections/{QDRANT_COLLECTION}/points/delete"
    try:
        async with httpx.AsyncClient(timeout=30, headers=_headers()) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        raise QdrantDeleteError(f"Qdrant delete request failed: {exc}") from exc
    if response.status_code >= 400:
        raise QdrantDeleteError(f"Qdrant delete failed: {response.status_code} {response.text[:500]}")
    return response.json()
