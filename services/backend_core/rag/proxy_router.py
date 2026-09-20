"""HSAAI RAG Proxy Router.

FIX B-06: All endpoints now require authentication and source tenant_id/workspace_id
from JWT claims instead of trusting client-supplied values. Previously any caller
could specify any tenant_id, enabling cross-tenant data access and deletion.
"""
import os, logging, httpx
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from pydantic import BaseModel

logger = logging.getLogger("hsaai.backend.rag_proxy")

router = APIRouter(prefix="/v1/rag", tags=["rag"])
RAG_URL = os.getenv("RAG_ENGINE_URL", "http://rag_engine:8030")

# FIX B-06: Add shared auth dependency.
import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..', '..', '..', '..', 'packages'))
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
    _AUTH_AVAILABLE = True
except ImportError as _e:
    _AUTH_AVAILABLE = False
    async def _auth_dep():  # type: ignore
        raise HTTPException(status_code=503, detail="Authentication module unavailable. Service cannot accept requests.")


class SearchPayload(BaseModel):
    query: str
    top_k: int = 8
    mode: str = "hybrid"
    # FIX B-06: tenant_id/workspace_id/user_id/user_roles removed — sourced from JWT.

class DocumentListPayload(BaseModel):
    limit: int = 50
    # FIX B-06: tenant_id/workspace_id/user_id/user_roles removed.

class AnalyticsPayload(BaseModel):
    # FIX B-06: tenant_id/workspace_id removed.
    start_date: str | None = None
    end_date: str | None = None


class AnswerPayload(SearchPayload):
    include_context: bool = True
    cite_sources: bool = True


@router.post("/upload")
@router.post("/documents/upload")
async def upload(
    file: UploadFile = File(...),
    visibility: str = Form("workspace"),
    allowed_roles: str = Form(""),
    allowed_users: str = Form(""),
    classification: str = Form("internal"),
    tags: str = Form(""),
    claims: dict = Depends(_auth_dep),  # FIX B-06: auth required
):
    # FIX B-06: tenant_id and workspace_id sourced from JWT, NOT form data.
    data = {
        "tenant_id": claims["tenant_id"],
        "workspace_id": claims.get("workspace_id", "default"),
        "user_id": claims["sub"],
        "user_roles": claims.get("roles", []),
        "visibility": visibility,
        "allowed_roles": allowed_roles,
        "allowed_users": allowed_users,
        "classification": classification,
        "tags": tags,
    }
    files = {"file": (file.filename, await file.read(), file.content_type or "application/octet-stream")}
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{RAG_URL}/v1/documents/upload", data=data, files=files)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return r.json()


@router.post("/search")
async def search(
    payload: SearchPayload,
    claims: dict = Depends(_auth_dep),  # FIX B-06: auth required
):
    body = payload.model_dump()
    # FIX B-06: Identity from JWT, not request body.
    body["tenant_id"] = claims["tenant_id"]
    body["workspace_id"] = claims.get("workspace_id", "default")
    body["user_id"] = claims["sub"]
    body["user_roles"] = claims.get("roles", [])
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{RAG_URL}/v1/search", json=body)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return r.json()


@router.post("/answer")
async def answer(
    payload: AnswerPayload,
    claims: dict = Depends(_auth_dep),  # FIX B-06: auth required
):
    body = payload.model_dump()
    body["tenant_id"] = claims["tenant_id"]
    body["workspace_id"] = claims.get("workspace_id", "default")
    body["user_id"] = claims["sub"]
    body["user_roles"] = claims.get("roles", [])
    async with httpx.AsyncClient(timeout=90) as client:
        r = await client.post(f"{RAG_URL}/v1/answer", json=body)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return r.json()


@router.post("/highlight")
async def highlight(
    payload: SearchPayload,
    claims: dict = Depends(_auth_dep),  # FIX B-06: auth required
):
    body = payload.model_dump()
    body["tenant_id"] = claims["tenant_id"]
    body["workspace_id"] = claims.get("workspace_id", "default")
    body["user_id"] = claims["sub"]
    body["user_roles"] = claims.get("roles", [])
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{RAG_URL}/v1/highlight", json=body)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return r.json()


@router.post("/documents")
async def list_documents(
    payload: DocumentListPayload,
    claims: dict = Depends(_auth_dep),  # FIX B-06: auth required
):
    body = payload.model_dump()
    body["tenant_id"] = claims["tenant_id"]
    body["workspace_id"] = claims.get("workspace_id", "default")
    body["user_id"] = claims["sub"]
    body["user_roles"] = claims.get("roles", [])
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{RAG_URL}/v1/documents", json=body)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return r.json()


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    claims: dict = Depends(_auth_dep),  # FIX B-06: auth required
):
    # FIX B-06: tenant_id from JWT — caller cannot delete another tenant's documents.
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.delete(
            f"{RAG_URL}/v1/documents/{doc_id}",
            params={
                "tenant_id": claims["tenant_id"],
                "workspace_id": claims.get("workspace_id", "default"),
            }
        )
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return r.json()


@router.post("/analytics")
async def analytics(
    payload: AnalyticsPayload,
    claims: dict = Depends(_auth_dep),  # FIX B-06: auth required
):
    body = payload.model_dump()
    body["tenant_id"] = claims["tenant_id"]
    body["workspace_id"] = claims.get("workspace_id", "default")
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{RAG_URL}/v1/analytics", json=body)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return r.json()
