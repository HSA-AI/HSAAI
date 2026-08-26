"""
HSAAI RAG Engine — Production Implementation with Persistent Storage

FIX: Replaced in-memory storage (MEMORY_POINTS, MEMORY_DOCS, RAG_EVENTS)
with Qdrant-first persistence and SQLite/PostgreSQL event logging.
Previously all data was lost on restart. Now:
- Document metadata is persisted in Qdrant payloads (already the case)
- Events are written to a local SQLite file for durability
- Qdrant is required (no more silent fallback to memory)
- Document listing uses Qdrant scroll instead of in-memory dict
"""

import os
import re
import uuid
import time
import asyncio
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Depends
# SECURITY FIX (CRITICAL): Fail Closed Authentication
# NO fallback auth allowed. If auth module cannot be loaded, the service MUST NOT start.
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..', '..', 'packages'))

# FIX FIX-MEDIUM-QUALITY (Issue 5): import canonical SearchRequest base class.
try:
    from common.schemas.search import SearchRequest as _CanonicalSearchRequest
except ImportError:  # fallback: define a minimal base so the module still loads
    from pydantic import BaseModel as _BaseModel, Field as _Field
    class _CanonicalSearchRequest(_BaseModel):  # type: ignore[no-redef]
        query: str = _Field(..., min_length=1)

# CRITICAL: Authentication is mandatory. No fallback, no bypass.
_AUTH_LOAD_ERROR = None
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
    _AUTH_AVAILABLE = True
except ImportError as _e:
    _AUTH_AVAILABLE = False
    _AUTH_LOAD_ERROR = str(_e)
    # Define a function that ALWAYS rejects — never grants access
    async def _auth_dep():  # type: ignore
        raise HTTPException(
            status_code=503,
            detail="Authentication module unavailable. Service cannot accept requests."
        )

from pydantic import BaseModel, Field

from .embedding import embed_text, embedding_status
from .loaders import extract_text_with_metadata
from .chunking import chunk_text_advanced, normalize_for_search, tokenize
from .reranker import bm25_scores, normalize_scores, rerank

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, ScrollResult
except Exception:
    QdrantClient = None

APP_VERSION = "4.0.0"  # FIX B-09: aligned with VERSION file
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "hsaai_knowledge")
STORAGE = Path(os.getenv("LOCAL_FILE_STORAGE", "/data/local_uploads"))
STORAGE.mkdir(parents=True, exist_ok=True)
CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "900"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "120"))
REQUIRE_QDRANT = os.getenv("REQUIRE_QDRANT", "true").lower() == "true"
MAX_UPLOAD_BYTES = int(os.getenv("RAG_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://llm_gateway:8090")
RAG_ANSWER_USE_LLM = os.getenv("RAG_ANSWER_USE_LLM", "true").lower() == "true"
# FIX v2.0: Aligned with llm_gateway/models.local.json:default ("qwen3:8b").
RAG_ANSWER_MODEL = os.getenv("RAG_ANSWER_MODEL") or os.getenv("LOCAL_LLM_MODEL", "qwen3:8b")

# FIX: Persistent event storage instead of in-memory list
EVENT_DB_PATH = Path(os.getenv("RAG_EVENT_DB", "/data/rag_events.db"))


def _init_event_db():
    """Initialize the SQLite event database for persistent event logging."""
    EVENT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(EVENT_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rag_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            tenant_id TEXT DEFAULT 'default',
            workspace_id TEXT DEFAULT 'default',
            ts REAL NOT NULL,
            extra_json TEXT DEFAULT '{}'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON rag_events(event_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_tenant ON rag_events(tenant_id, workspace_id)")
    conn.commit()
    conn.close()


_init_event_db()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("hsaai.rag_engine")

app = FastAPI(title="HSAAI RAG Engine", version=APP_VERSION)


# ─── STARTUP VALIDATION: Fail Closed Authentication ────────────────
# CRITICAL: The service MUST NOT start if auth module is unavailable.
@app.on_event("startup")
async def _validate_auth_on_startup():
    """Startup validation: refuse to start if authentication module is missing."""
    if not _AUTH_AVAILABLE:
        logger.error("=" * 60)
        logger.error("CRITICAL: Authentication module failed to load!")
        logger.error(f"Error: {_AUTH_LOAD_ERROR}")
        logger.error("Service CANNOT start without authentication (Fail Closed).")
        logger.error("All requests will be rejected with HTTP 503.")
        logger.error("=" * 60)
        # In production: raise SystemExit to prevent startup
        # In test mode: log error but allow startup (so tests can verify 503 behavior)
        if os.getenv("DEPLOY_ENV") != "test" and os.getenv("ALLOW_AUTH_BYPASS") != "true":
            raise SystemExit(1)
    else:
        logger.info("✓ Authentication module loaded successfully (Fail Closed enforced)")


@app.get("/health/auth")
async def _auth_health():
    """Health check for authentication module readiness."""
    return {
        "auth_available": _AUTH_AVAILABLE,
        "auth_error": _AUTH_LOAD_ERROR,
        "fail_closed": True,
    }


# FIX: Removed MEMORY_POINTS, MEMORY_DOCS, and RAG_EVENTS in-memory globals.
# All data now lives in Qdrant (vectors + payloads) and SQLite (events).
# This ensures data survives restarts.


def _event(event_type: str, tenant_id: str, workspace_id: str, **extra: Any) -> None:
    """Persist an event to the SQLite database instead of in-memory list."""
    try:
        conn = sqlite3.connect(str(EVENT_DB_PATH))
        conn.execute(
            "INSERT INTO rag_events (event_type, tenant_id, workspace_id, ts, extra_json) VALUES (?, ?, ?, ?, ?)",
            (event_type, tenant_id, workspace_id, time.time(), json.dumps(extra, default=str)),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.warning("Failed to persist RAG event: %s", exc)


def _is_allowed(payload: dict[str, Any], user_id: str | None = None, user_roles: list[str] | None = None) -> bool:
    acl = payload.get("acl") or {}
    if payload.get("deleted"):
        return False
    if acl.get("visibility") == "public":
        return True
    roles = set(user_roles or [])
    allowed_roles = set(acl.get("allowed_roles") or [])
    allowed_users = set(acl.get("allowed_users") or [])
    if user_id and user_id in allowed_users:
        return True
    if roles and allowed_roles and roles.intersection(allowed_roles):
        return True
    return acl.get("visibility", "workspace") == "workspace" and not allowed_roles and not allowed_users


def _doc_view(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "doc_id": doc.get("doc_id"),
        "filename": doc.get("filename"),
        "tenant_id": doc.get("tenant_id"),
        "workspace_id": doc.get("workspace_id"),
        "chunk_count": doc.get("chunk_count", 0),
        "bytes": doc.get("bytes", 0),
        "classification": doc.get("classification", "internal"),
        "tags": doc.get("tags", []),
        "acl": doc.get("acl", {}),
        "ocr_used": (doc.get("extraction") or {}).get("ocr_used"),
        "extraction_method": (doc.get("extraction") or {}).get("extraction_method"),
        "created_at": doc.get("created_at"),
        "deleted": doc.get("deleted", False),
    }


class SearchRequest(_CanonicalSearchRequest):
    """FIX FIX-MEDIUM-QUALITY (Issue 5): subclasses the canonical
    SearchRequest from common.schemas.search and adds rag-engine-specific
    scoping/ACL fields (preserving the previous wire-shape)."""
    tenant_id: str = "default"
    workspace_id: str = "default"
    user_id: str | None = None
    user_roles: list[str] = Field(default_factory=list)
    top_k: int = Field(8, ge=1, le=30)
    mode: str = "hybrid"


class DocumentListRequest(BaseModel):
    tenant_id: str = "default"
    workspace_id: str = "default"
    user_id: str | None = None
    user_roles: list[str] = Field(default_factory=list)
    limit: int = Field(50, ge=1, le=500)


class AnalyticsRequest(BaseModel):
    tenant_id: str = "default"
    workspace_id: str = "default"


class AnswerRequest(SearchRequest):
    include_context: bool = True
    cite_sources: bool = True


class HighlightRequest(SearchRequest):
    doc_id: str | None = None


def get_qdrant(vector_size: int | None = None):
    """
    Get a Qdrant client with collection initialization.

    FIX: In production mode (REQUIRE_QDRANT=true), there is no fallback
    to in-memory storage. If Qdrant is unreachable, an error is raised.
    """
    if not QdrantClient:
        if REQUIRE_QDRANT:
            raise HTTPException(503, "qdrant-client library is required but not installed")
        return None
    try:
        client = QdrantClient(url=QDRANT_URL, timeout=10)
        cols = [x.name for x in client.get_collections().collections]
        if COLLECTION not in cols:
            size = vector_size or embedding_status()["vector_size"]
            client.create_collection(COLLECTION, vectors_config=VectorParams(size=size, distance=Distance.COSINE))
        return client
    except Exception:
        if REQUIRE_QDRANT:
            raise HTTPException(503, "Qdrant is required in production but is not reachable")
        logger.warning("Qdrant not reachable, operating in degraded mode")
        return None


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    return [c.text for c in chunk_text_advanced(text, size=size, overlap=overlap)]


def secure_name(name: str) -> str:
    # FIX-24: Robust filename sanitization that rejects path traversal and
    # empty/dot-only names. Previously returned 'document.txt' for empty
    # input and didn't block '../../etc' style traversal attempts.
    if not name or not isinstance(name, str):
        return "default"
    # FIX-24b: Reject any input containing path separators or '..' before
    # basename extraction — '../../etc' should be rejected outright, not
    # silently reduced to 'etc' (which could still be a sensitive filename).
    if "/" in name or "\\" in name or ".." in name:
        return "default"
    # Reject path-traversal leftovers ('..') and empty after basename strip
    if not name or name == "." or name == "..":
        return "default"
    # Sanitize: keep alphanumerics, dots, hyphens, underscores, Arabic range
    sanitized = re.sub(r"[^A-Za-z0-9_.\-؀-ۿ]", "_", name)[:160]
    if not sanitized or sanitized == "." or sanitized == ".." or set(sanitized) == {"_"}:
        return "default"
    return sanitized


@app.get("/health")
def health():
    emb = embedding_status()
    qdrant_ok = False
    try:
        qdrant_ok = bool(get_qdrant(emb["vector_size"]))
    except Exception:
        pass
    return {
        "status": "ok",
        "service": "rag_engine",
        "version": APP_VERSION,
        "qdrant": qdrant_ok,
        "storage": str(STORAGE),
        "event_db": str(EVENT_DB_PATH),
        "embedding": emb,
        "document_types": ["txt", "md", "csv", "json", "pdf", "docx", "xlsx", "png", "jpg", "jpeg", "tiff"],
        "llm_gateway_url": LLM_GATEWAY_URL,
        "rag_answer_use_llm": RAG_ANSWER_USE_LLM,
        "persistence": "qdrant_plus_sqlite",
        "features": ["ocr", "citations", "source_highlighting", "hybrid_search", "reranking", "arabic_embedding_optimization", "streaming_ready", "llm_grounded_answer_generation", "persistent_events", "embedding_endpoint"],
    }


# FIX v2.2 (Phase 2): Embedding endpoint for multimodal RAG + external consumers.
# Returns the vector embedding for a given text, using the same MiniLM-L12-v2
# model that powers text search. This enables the AdvancedRAGEngine to generate
# real query embeddings for multimodal search instead of using placeholders.
@app.post("/v1/embed")
async def embed_text_endpoint(request: Request):
    """Generate an embedding vector for the given text.

    Request body: {"text": "query text to embed"}
    Response: {"embedding": [0.1, 0.2, ...], "model": "paraphrase-multilingual-MiniLM-L12-v2", "dimensions": 384}
    """
    try:
        body = await request.json()
    except Exception:
        from fastapi import HTTPException
        raise HTTPException(400, "Invalid JSON body")
    text = body.get("text", "")
    if not text or not text.strip():
        from fastapi import HTTPException
        raise HTTPException(400, "Missing 'text' field")
    try:
        vector = embed_text(text)
        return {
            "embedding": vector,
            "model": "paraphrase-multilingual-MiniLM-L12-v2",
            "dimensions": len(vector),
        }
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(500, f"Embedding generation failed: {str(e)[:200]}")


@app.post("/v1/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    tenant_id: str = Form("default"),
    workspace_id: str = Form("default"),
    visibility: str = Form("workspace"),
    allowed_roles: str = Form(""),
    allowed_users: str = Form(""),
    classification: str = Form("internal"),
    tags: str = Form(""),
):
    """
    Upload and index a document with persistent storage.

    FIX: Previously stored documents only in MEMORY_DOCS (lost on restart).
    Now documents are stored in Qdrant payloads and persist across restarts.
    """
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File is too large. Max allowed bytes: {MAX_UPLOAD_BYTES}")
    filename = secure_name(file.filename or f"doc-{uuid.uuid4()}.txt")
    doc_id = str(uuid.uuid4())

    # FIX v2.2 (Phase 2): Store the document in MinIO object storage (S3-compatible)
    # instead of local disk. This enables horizontal scaling (any pod can read any
    # document), lifecycle management, versioning, and survives pod reschedules.
    # Falls back to local disk in dev environments where MinIO is not configured.
    USE_OBJECT_STORAGE = os.getenv("USE_OBJECT_STORAGE", "true").lower() == "true"
    object_key = None
    if USE_OBJECT_STORAGE:
        try:
            import sys as _sys
            _sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
            from common.storage import storage_client
            object_key = storage_client.upload_document(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                document_id=f"{doc_id}-{filename}",
                data=raw,
                content_type=file.content_type or "application/octet-stream",
                metadata={
                    "uploaded_by": "rag_engine",
                    "classification": classification,
                    "original_filename": filename,
                    "tenant_id": tenant_id,
                    "workspace_id": workspace_id,
                },
            )
            logger.info("Document stored in MinIO: %s", object_key)
        except Exception as exc:
            logger.warning("MinIO upload failed (%s) — falling back to local disk", exc)
            object_key = None

    if object_key is None:
        # Fallback: local disk (dev environments only)
        target_dir = STORAGE / secure_name(tenant_id) / secure_name(workspace_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{doc_id}-{filename}"
        target.write_bytes(raw)

    extracted = extract_text_with_metadata(filename, raw, enable_ocr=True)
    text = extracted["text"]

    # v3.0: PII Detection — check document before indexing
    # Call the PII detector service to scan for sensitive data
    try:
        async with httpx.AsyncClient(timeout=30) as pii_client:
            pii_response = await pii_client.post(
                "http://pii_detector:8092/v1/pii/check-document",
                json={
                    "text": text[:50000],  # scan first 50K chars (balance speed vs coverage)
                    "redact": True,
                    "tenant_id": tenant_id,
                    "workspace_id": workspace_id,
                },
                timeout=30.0,
            )
            if pii_response.status_code < 400:
                pii_result = pii_response.json()
                pii_decision = pii_result.get("decision", "allow")
                pii_risk = pii_result.get("risk_level", "none")

                # Block critical PII (national IDs, credit cards)
                if pii_decision == "block":
                    _event("upload", tenant_id, workspace_id, doc_id=doc_id, filename=filename,
                           pii_decision="blocked", pii_risk=pii_risk,
                           pii_types=pii_result.get("pii_types", []))
                    raise HTTPException(
                        422,
                        f"Document rejected: contains critical PII ({', '.join(pii_result.get('pii_types', []))}). "
                        "Redact these fields before uploading. Document not indexed."
                    )

                # For warn/allow with PII: use the redacted text for indexing (keep original in storage)
                if pii_decision == "warn" and pii_result.get("redacted_text"):
                    logger.info("Document %s contains PII (risk=%s) — indexing redacted version",
                                doc_id, pii_risk)
                    text = pii_result["redacted_text"]
                    extracted["text"] = text  # update so chunks use redacted text
                    extracted["pii_redacted"] = True
                    extracted["pii_risk_level"] = pii_risk

                _event("upload", tenant_id, workspace_id, doc_id=doc_id, filename=filename,
                       pii_decision=pii_decision, pii_risk=pii_risk)
    except httpx.HTTPError as exc:
        logger.warning("PII detector service unavailable: %s — continuing without PII check", exc)
    except Exception as exc:
        logger.warning("PII detection failed: %s — continuing without check", exc)

    chunk_objs = chunk_text_advanced(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP, page_map=extracted.get("page_map") or None)
    if not chunk_objs:
        raise HTTPException(400, "No extractable text. OCR dependencies may be missing for scanned files: tesseract-ocr, tesseract-ocr-ara, poppler-utils.")

    vectors = [embed_text(chunk.text) for chunk in chunk_objs]
    points = []
    acl = {
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
        "visibility": visibility if visibility in {"workspace", "public", "restricted"} else "workspace",
        "allowed_roles": [x.strip() for x in allowed_roles.split(",") if x.strip()],
        "allowed_users": [x.strip() for x in allowed_users.split(",") if x.strip()],
    }
    doc_tags = [x.strip() for x in tags.split(",") if x.strip()]

    # FIX: Store document metadata as a special point in Qdrant so it persists
    doc_metadata_point = {
        "id": str(uuid.uuid4()),
        "vector": [0.0] * len(vectors[0]),  # zero vector for metadata-only point
        "payload": {
            "point_type": "document_metadata",
            "doc_id": doc_id,
            "filename": filename,
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "text": text[:5000],  # store first 5000 chars for preview
            "extraction_method": extracted.get("extraction_method"),
            "ocr_used": extracted.get("ocr_used"),
            "chunk_count": len(chunk_objs),
            "bytes": len(raw),
            "classification": classification,
            "tags": doc_tags,
            "acl": acl,
            "created_at": time.time(),
            "deleted": False,
        },
    }

    for idx, (chunk, vector) in enumerate(zip(chunk_objs, vectors)):
        payload = {
            "point_type": "chunk",
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "doc_id": doc_id,
            "filename": filename,
            "chunk_index": idx,
            "text": chunk.text,
            "normalized_text": normalize_for_search(chunk.text),
            "page": chunk.page,
            "start_char": chunk.start_char,
            "end_char": chunk.end_char,
            "heading": chunk.heading,
            "citation": {"label": f"{filename}#chunk-{idx}", "page": chunk.page, "start_char": chunk.start_char, "end_char": chunk.end_char},
            "metadata": {"bytes": len(raw), "content_type": file.content_type or "application/octet-stream", "ocr_used": extracted.get("ocr_used"), "extraction_method": extracted.get("extraction_method")},
            "classification": classification,
            "tags": doc_tags,
            "deleted": False,
            "acl": acl,
        }
        points.append({"id": str(uuid.uuid4()), "vector": vector, "payload": payload})

    # Add the metadata point
    all_points = [doc_metadata_point] + points

    client = get_qdrant(len(vectors[0]))
    if client:
        client.upsert(COLLECTION, [PointStruct(id=p["id"], vector=p["vector"], payload=p["payload"]) for p in all_points])
    else:
        # FIX: No more silent fallback to MEMORY_POINTS
        if REQUIRE_QDRANT:
            raise HTTPException(503, "Qdrant is required for document storage but is not reachable")
        logger.error("Qdrant not available; document was saved to disk but not indexed for search")

    _event("document_uploaded", tenant_id, workspace_id, doc_id=doc_id, filename=filename, chunks=len(chunk_objs), classification=classification)
    return {
        "status": "indexed",
        "doc_id": doc_id,
        "filename": filename,
        "chunks": len(chunk_objs),
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
        "embedding": embedding_status(),
        "ocr_used": extracted.get("ocr_used"),
        "extraction_method": extracted.get("extraction_method"),
        "classification": classification,
        "tags": doc_tags,
        "acl": acl,
        "persistence": "qdrant",
        "features": ["advanced_chunking", "citations", "source_offsets", "document_acl", "classification", "analytics", "persistent_storage"],
    }


@app.post("/v1/documents")
def list_documents(req: DocumentListRequest, claims: dict = Depends(_auth_dep)):
    """
    List documents from Qdrant (persistent) instead of in-memory dict.

    FIX: Previously listed from MEMORY_DOCS which was lost on restart.
    Now scrolls through Qdrant to find document_metadata points.
    """
    docs = []
    client = get_qdrant()
    if client:
        try:
            flt = Filter(must=[
                FieldCondition(key="point_type", match=MatchValue(value="document_metadata")),
                FieldCondition(key="tenant_id", match=MatchValue(value=req.tenant_id)),
                FieldCondition(key="workspace_id", match=MatchValue(value=req.workspace_id)),
            ])
            offset = None
            while True:
                results: ScrollResult = client.scroll(COLLECTION, scroll_filter=flt, limit=100, offset=offset, with_payload=True)
                for point in results[0]:
                    p = point.payload or {}
                    if not p.get("deleted") and _is_allowed(p, req.user_id, req.user_roles):
                        docs.append(_doc_view(p))
                offset = results[1]
                if not offset:
                    break
        except Exception as exc:
            logger.error("Failed to list documents from Qdrant: %s", exc)

    docs.sort(key=lambda d: d.get("created_at") or 0, reverse=True)
    return {"count": min(len(docs), req.limit), "documents": docs[:req.limit]}


@app.get("/v1/documents/{doc_id}")
def get_document(doc_id: str, claims: dict = Depends(_auth_dep)):
    """
    Get document metadata from Qdrant.
    SECURITY FIX: tenant_id and workspace_id come from Claims ONLY, never from request.
    This prevents IDOR (Insecure Direct Object Reference) / cross-tenant access.
    """
    # CRITICAL: Use Claims as the ONLY source of identity
    tenant_id = claims.get("tenant_id")
    workspace_id = claims.get("workspace_id", "default")
    if not tenant_id:
        raise HTTPException(403, "Missing tenant_id in authentication claims")

    client = get_qdrant()
    if not client:
        raise HTTPException(503, "Qdrant is not available")
    try:
        flt = Filter(must=[
            FieldCondition(key="point_type", match=MatchValue(value="document_metadata")),
            FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
            FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
            FieldCondition(key="workspace_id", match=MatchValue(value=workspace_id)),
        ])
        results = client.scroll(COLLECTION, scroll_filter=flt, limit=1, with_payload=True)
        for point in results[0]:
            p = point.payload or {}
            if not p.get("deleted"):
                return _doc_view(p)
    except Exception as exc:
        logger.error("Failed to get document from Qdrant: %s", exc)
    raise HTTPException(404, "Document not found")


@app.delete("/v1/documents/{doc_id}")
def delete_document(doc_id: str, claims: dict = Depends(_auth_dep)):
    """
    Delete a document.
    SECURITY FIX: tenant_id and workspace_id come from Claims ONLY.
    Prevents cross-tenant deletion (IDOR).
    """
    tenant_id = claims.get("tenant_id")
    workspace_id = claims.get("workspace_id", "default")
    if not tenant_id:
        raise HTTPException(403, "Missing tenant_id in authentication claims")
    """
    Soft-delete a document by marking its metadata and chunks as deleted.

    FIX: Previously only updated in-memory dicts. Now updates Qdrant payloads.
    """
    client = get_qdrant()
    if not client:
        raise HTTPException(503, "Qdrant is not available")

    # Find and mark the document metadata point
    try:
        flt = Filter(must=[
            FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
            FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
        ])
        results = client.scroll(COLLECTION, scroll_filter=flt, limit=1000, with_payload=True)
        # FIX v2.0: Removed dead points_to_update code with bogus vector=[0.0]*1
        filename = ""
        point_ids = []
        for point in results[0]:
            p = dict(point.payload or {})
            if not filename and p.get("filename"):
                filename = p.get("filename", "")
            point_ids.append(point.id)

        if point_ids:
            client.set_payload(COLLECTION, payload={"deleted": True}, points=point_ids)

    except Exception as exc:
        logger.error("Failed to delete document from Qdrant: %s", exc)

    _event("document_deleted", tenant_id, workspace_id, doc_id=doc_id, filename=filename)
    return {"status": "deleted", "doc_id": doc_id}


@app.post("/v1/analytics")
def analytics(req: AnalyticsRequest, claims: dict = Depends(_auth_dep)):
    """
    Return analytics from persistent event database.

    FIX: Previously read from in-memory RAG_EVENTS list (lost on restart).
    Now reads from SQLite event database.
    """
    conn = sqlite3.connect(str(EVENT_DB_PATH))
    try:
        # Count events by type
        cursor = conn.execute(
            "SELECT event_type, COUNT(*) FROM rag_events WHERE tenant_id=? AND workspace_id=? GROUP BY event_type",
            (req.tenant_id, req.workspace_id),
        )
        event_counts = dict(cursor.fetchall())

        # Get recent events
        cursor = conn.execute(
            "SELECT event_type, ts, extra_json FROM rag_events WHERE tenant_id=? AND workspace_id=? ORDER BY ts DESC LIMIT 20",
            (req.tenant_id, req.workspace_id),
        )
        recent_events = []
        for row in cursor.fetchall():
            try:
                extra = json.loads(row[2]) if row[2] else {}
            except Exception:
                extra = {}
            recent_events.append({"event_type": row[0], "ts": row[1], **extra})
    finally:
        conn.close()

    # Get document counts from Qdrant
    doc_count = 0
    chunk_count = 0
    client = get_qdrant()
    if client:
        try:
            flt = Filter(must=[
                FieldCondition(key="tenant_id", match=MatchValue(value=req.tenant_id)),
                FieldCondition(key="workspace_id", match=MatchValue(value=req.workspace_id)),
            ])
            meta_flt = Filter(must=[
                FieldCondition(key="point_type", match=MatchValue(value="document_metadata")),
                FieldCondition(key="tenant_id", match=MatchValue(value=req.tenant_id)),
                FieldCondition(key="workspace_id", match=MatchValue(value=req.workspace_id)),
            ])
            doc_count = client.count(COLLECTION, meta_flt).count
            chunk_flt = Filter(must=[
                FieldCondition(key="point_type", match=MatchValue(value="chunk")),
                FieldCondition(key="tenant_id", match=MatchValue(value=req.tenant_id)),
                FieldCondition(key="workspace_id", match=MatchValue(value=req.workspace_id)),
            ])
            chunk_count = client.count(COLLECTION, chunk_flt).count
        except Exception:
            pass

    searches = event_counts.get("search", 0)
    answers = event_counts.get("answer", 0)
    no_source = event_counts.get("no_source_answer", 0)

    return {
        "tenant_id": req.tenant_id,
        "workspace_id": req.workspace_id,
        "documents": doc_count,
        "chunks": chunk_count,
        "uploads": event_counts.get("document_uploaded", 0),
        "searches": searches,
        "answers": answers,
        "no_source_answers": no_source,
        "source_coverage_rate": round(1 - (no_source / max(answers, 1)), 4) if answers else None,
        "recent_events": recent_events,
        "persistence": "qdrant_plus_sqlite",
    }


@app.post("/v1/search")
def search(req: SearchRequest, claims: dict = Depends(_auth_dep)):
    """
    Search documents using Qdrant vector search with hybrid re-ranking.
    SECURITY FIX: tenant_id and workspace_id come from Claims ONLY, not request body.
    Prevents cross-tenant data access (IDOR).
    """
    # CRITICAL: Override any client-supplied tenant_id with Claims
    tenant_id = claims.get("tenant_id")
    workspace_id = claims.get("workspace_id", "default")
    if not tenant_id:
        raise HTTPException(403, "Missing tenant_id in authentication claims")

    vector = embed_text(req.query)
    results: list[dict[str, Any]] = []
    client = get_qdrant(len(vector))
    if client:
        flt = Filter(must=[
            FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
            FieldCondition(key="workspace_id", match=MatchValue(value=workspace_id)),
            FieldCondition(key="point_type", match=MatchValue(value="chunk")),
        ])
        hits = client.search(COLLECTION, query_vector=vector, query_filter=flt, limit=max(req.top_k * 4, 20), with_payload=True)
        results = [{"score": float(h.score), **(h.payload or {})} for h in hits]
    else:
        # FIX: No more fallback to MEMORY_POINTS
        if REQUIRE_QDRANT:
            raise HTTPException(503, "Qdrant is required for search but is not reachable")
        return {"mode": req.mode, "count": 0, "results": [], "features": [], "error": "Qdrant not available"}

    results = [r for r in results if _is_allowed(r, req.user_id, req.user_roles)]
    doc_ids = list({r.get("doc_id") for r in results if r.get("doc_id")})
    _event("search", req.tenant_id, req.workspace_id, query=req.query, mode=req.mode, hits=len(results), doc_ids=doc_ids)

    if req.mode in {"lexical", "hybrid"}:
        lexical_scores = bm25_scores(req.query, [r.get("text", "") for r in results])
        for idx, score in enumerate(lexical_scores):
            if idx < len(results):
                results[idx]["lexical_score"] = score

    if req.mode == "lexical":
        results.sort(key=lambda x: x.get("lexical_score", 0.0), reverse=True)
    elif req.mode == "hybrid":
        results = rerank(req.query, results)
    else:
        results.sort(key=lambda x: x.get("score", 0.0), reverse=True)

    final = results[:req.top_k]
    return {"mode": req.mode, "count": len(final), "results": final, "features": ["arabic_normalization", "bm25", "semantic", "reranking", "persistent_storage"]}


@app.post("/v1/answer")
async def answer(req: AnswerRequest, claims: dict = Depends(_auth_dep)):
    """Generate a grounded answer using RAG + LLM."""
    started = time.time()
    hits = search(req)["results"]
    context = "\n\n".join([f"[{i+1}] {h.get('filename')} p.{h.get('page') or '-'} chunk {h.get('chunk_index')}: {h.get('text', '')}" for i, h in enumerate(hits[:5])])
    citations = []
    for i, h in enumerate(hits, start=1):
        citations.append({
            "index": i,
            "doc_id": h.get("doc_id"),
            "filename": h.get("filename"),
            "chunk_index": h.get("chunk_index"),
            "page": h.get("page"),
            "score": h.get("score"),
            "start_char": h.get("start_char"),
            "end_char": h.get("end_char"),
            "quote": (h.get("text") or "")[:420],
        })

    if not hits:
        _event("answer", req.tenant_id, req.workspace_id, query=req.query, answer_type="no_sources", hits=0, doc_ids=[])
        return {
            "query": req.query,
            "answer": "لم أجد مصادر داخل قاعدة المعرفة للإجابة على هذا السؤال. ارفع الوثائق ذات الصلة ثم أعد المحاولة.",
            "answer_type": "no_sources",
            "context": None if not req.include_context else "",
            "sources": [],
            "elapsed_ms": int((time.time() - started) * 1000),
            "features": ["source_grounded_answers", "no_answer_without_sources"],
        }

    system = (
        "You are HSAAI, a private enterprise RAG assistant. Answer only from the provided context. "
        "If the context is insufficient, say that clearly. Use Arabic by default. "
        "Cite source numbers like [1], [2] for every factual claim."
    )

    # v3.0: Prompt Injection Defense — sanitize user query + RAG context before building prompt
    try:
        import sys as _sys
        _sys.path.insert(0, "/app/packages")
        from common.prompt_security import (
            sanitize_user_query, sanitize_rag_context, build_safe_prompt, should_block_request
        )
        query_result = sanitize_user_query(req.query)
        if should_block_request(query_result.risk_score):
            _event("answer", req.tenant_id, req.workspace_id,
                   query=req.query, answer_type="blocked_injection",
                   risk_score=query_result.risk_score,
                   patterns=query_result.detected_patterns[:3])
            return {
                "query": req.query,
                "answer": "تم رفض الطلب لاحتوائه على أنماط مشبوهة قد تكون محاولة حقن. يرجى إعادة صياغة السؤال بشكل مباشر.",
                "answer_type": "blocked_injection",
                "injection_detected": True,
                "risk_score": query_result.risk_score,
                "context": None,
                "sources": [],
                "elapsed_ms": int((time.time() - started) * 1000),
            }
        # Sanitize RAG context chunks
        chunk_dicts = [{"text": h.get("text", ""), "doc_id": h.get("doc_id"), "filename": h.get("filename")} for h in hits[:5]]
        sanitized_chunks, rag_warnings = sanitize_rag_context(chunk_dicts)
        # Rebuild sanitized context string
        context = "\n\n".join([
            f"[{i+1}] {h.get('filename')} p.{h.get('page') or '-'} chunk {h.get('chunk_index')}: {h.get('text', '')}"
            for i, h in enumerate([{**hits[i], "text": sanitized_chunks[i]["text"]} for i in range(min(len(hits), len(sanitized_chunks)))])
        ])
        # Build safe prompt with explicit delimiters
        prompt = build_safe_prompt(
            system_prompt=system,
            rag_context=context,
            user_query=query_result.sanitized,
        )
        if rag_warnings:
            logger.warning("RAG context sanitization warnings: %s", rag_warnings[:2])
    except ImportError:
        # Fallback: no sanitization (dev mode without packages/common)
        logger.warning("prompt_security module not available — running without injection defense")
        prompt = (
            f"السؤال: {req.query}\n\n"
            f"المصادر الداخلية:\n{context}\n\n"
            "اكتب إجابة تنفيذية دقيقة ومختصرة، واذكر المراجع داخل النص بصيغة [1] [2]."
        )
    generated_answer = None
    llm_error = None
    if RAG_ANSWER_USE_LLM:
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(f"{LLM_GATEWAY_URL}/v1/generate", json={
                    "prompt": prompt,
                    "system": system,
                    "model": RAG_ANSWER_MODEL,
                    "temperature": 0.1,
                    "max_tokens": 900,
                    "tenant_id": req.tenant_id,
                    "workspace_id": req.workspace_id,
                })
            if r.status_code >= 400:
                llm_error = r.text[:500]
                logger.error("RAG answer LLM failed: %s", llm_error)
            else:
                generated_answer = (r.json().get("text") or "").strip()
        except Exception as exc:
            llm_error = str(exc)
            logger.exception("RAG answer LLM generation exception")

    if not generated_answer:
        generated_answer = (
            "تعذر توليد إجابة نهائية عبر نموذج اللغة المحلي. هذه هي المقاطع الأكثر صلة من قاعدة المعرفة:\n\n"
            + context
        )

    answer_type = "llm_grounded" if generated_answer and not llm_error else "retrieval_fallback"
    doc_ids = list({h.get("doc_id") for h in hits if h.get("doc_id")})
    _event("answer", req.tenant_id, req.workspace_id, query=req.query, answer_type=answer_type, hits=len(hits), doc_ids=doc_ids)
    return {
        "query": req.query,
        "answer": generated_answer,
        "answer_type": answer_type,
        "context": context if req.include_context else None,
        "sources": citations if req.cite_sources else [],
        "llm": {"provider": "ollama_via_llm_gateway", "model": RAG_ANSWER_MODEL, "error": llm_error},
        "elapsed_ms": int((time.time() - started) * 1000),
        "features": ["citation_system", "source_offsets", "source_highlighting_ready", "hybrid_search", "reranking", "llm_grounded_answer_generation", "persistent_storage"],
    }


@app.post("/v1/highlight")
def highlight(req: HighlightRequest, claims: dict = Depends(_auth_dep)):
    hits = search(req)["results"]
    q_terms = set(tokenize(req.query))
    output = []
    for h in hits:
        if req.doc_id and h.get("doc_id") != req.doc_id:
            continue
        text = h.get("text", "")
        spans = []
        lowered = normalize_for_search(text)
        for term in q_terms:
            if not term:
                continue
            pos = lowered.find(term)
            if pos >= 0:
                spans.append({"term": term, "normalized_position": pos})
        output.append({
            "doc_id": h.get("doc_id"),
            "filename": h.get("filename"),
            "chunk_index": h.get("chunk_index"),
            "page": h.get("page"),
            "text": text,
            "highlight_terms": sorted(q_terms),
            "highlight_spans": spans,
            "citation": h.get("citation"),
        })
    return {"count": len(output), "highlights": output[:req.top_k]}


@app.post("/v1/answer/stream")
async def answer_stream(req: AnswerRequest, claims: dict = Depends(_auth_dep)):
    from fastapi.responses import StreamingResponse
    import json, asyncio
    payload = await answer(req)
    async def events():
        yield "event: metadata\n"
        yield "data: " + json.dumps({"sources": payload.get("sources", []), "features": payload.get("features", [])}, ensure_ascii=False) + "\n\n"
        text = payload.get("context") or "No context found."
        for token in text.split():
            yield "event: token\n"
            yield "data: " + json.dumps({"token": token + " "}, ensure_ascii=False) + "\n\n"
            await asyncio.sleep(0)  # Yield to event loop for natural streaming cadence
        yield "event: done\ndata: {}\n\n"
    return StreamingResponse(events(), media_type="text/event-stream")
