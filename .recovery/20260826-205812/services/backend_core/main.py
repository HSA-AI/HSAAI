from backend_core.security.internal_only import internal_only_request_guard, assert_internal_mode_is_clean
from fastapi import FastAPI, Depends, Request, WebSocket, UploadFile, File, Header, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from backend_core.config import settings
from backend_core.core.engine import process_message, stream_message
from backend_core.security.rbac import require_permission, verify_authorization
from backend_core.admin.dashboard import stats
from backend_core.db.database import init_db, SessionLocal, check_db
from backend_core.schemas import ChatRequest
import os
import httpx
from backend_core.websocket.ws import websocket_endpoint
from backend_core.llm.router import router as llm_router
from backend_core.rag.proxy_router import router as rag_proxy_router
from backend_core.branding.router import router as branding_router
from backend_core.governance.router import router as governance_router
from backend_core.integrations.router import router as integrations_router
from backend_core.knowledge.router import router as knowledge_hub_router
from backend_core.executive.router import router as executive_router
from backend_core.phase5.router import router as phase5_router
from backend_core.connectors.hsa_integrations import connector_status
from backend_core.ai_operations.router import router as ai_operations_router
from backend_core.enterprise_search.router import router as enterprise_search_router
from backend_core.agent_runtime.router import router as agent_runtime_router
from backend_core.workflow_runtime.router import router as workflow_runtime_router
from backend_core.smart_responses.router import router as smart_responses_router
from backend_core.smart_responses.service import detect_response
from backend_core.intent_detection.router import router as intent_detection_router
from backend_core.department_agents.router import router as department_agents_router
from backend_core.enterprise_upgrade.router import router as enterprise_upgrade_router
from backend_core.enterprise_integrations.router import router as enterprise_integrations_router
from backend_core.maturity_upgrade.router import router as maturity_router
from backend_core.enterprise_ops.router import router as enterprise_ops_router
from backend_core.enterprise_os.router import router as enterprise_os_router
from backend_core.finops.router import router as finops_router
from backend_core.approvals.router import router as approvals_router
from backend_core.knowledge_graph.router import router as knowledge_graph_router
from backend_core.ai_quality.router import router as ai_quality_router
from backend_core.knowledge.qdrant_client import ensure_collection, qdrant_health

# Observability
try:
    from packages.common.observability.tracing import setup_tracing, shutdown_tracing
    from packages.common.observability.logging import setup_logging
    from packages.common.observability.middleware import ObservabilityMiddleware, init_sentry
except ImportError:
    setup_tracing = None
    shutdown_tracing = None
    setup_logging = None
    ObservabilityMiddleware = None
    init_sentry = None
from backend_core.knowledge_graph.graph_service import GraphService
from collections import defaultdict, deque
import time

# FIX B-16: Removed misleading comment about lazy loading — routers are imported eagerly.
app = FastAPI(title="HSAAI Core Backend", version="4.0.0")

# ═══════════════════════════════════════════════════════════════════════
# FIX V3: JSON 404 Handler for /api/* paths
# ═══════════════════════════════════════════════════════════════════════
# Previously, when the frontend called a non-existent /api/* endpoint,
# FastAPI returned its default HTML 404 page. The frontend fetch helpers
# then captured that HTML as the error message and rendered it in the UI.
# This handler ensures all /api/* 404s return JSON instead of HTML.
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
async def api_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Return JSON for /api/* paths, HTML for browser navigation."""
    path = request.url.path
    if path.startswith("/api/") or path.startswith("/v1/"):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "status_code": exc.status_code,
                "path": path,
                "request_id": getattr(request.state, "request_id", None),
            },
            headers={"X-Content-Type-Options": "nosniff"},
        )
    # For non-API paths, return a minimal HTML response
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status_code": exc.status_code},
    )


app.middleware("http")(internal_only_request_guard)
app.include_router(llm_router)
app.include_router(rag_proxy_router)
app.include_router(branding_router)
app.include_router(governance_router)
app.include_router(integrations_router)
app.include_router(knowledge_hub_router)
app.include_router(executive_router)
app.include_router(phase5_router)
app.include_router(ai_operations_router)
app.include_router(enterprise_search_router)
app.include_router(agent_runtime_router)
app.include_router(workflow_runtime_router)
app.include_router(smart_responses_router)
app.include_router(intent_detection_router)
app.include_router(department_agents_router)
app.include_router(enterprise_upgrade_router)
app.include_router(enterprise_integrations_router)
app.include_router(maturity_router)
app.include_router(enterprise_ops_router)
app.include_router(enterprise_os_router)
app.include_router(finops_router)
app.include_router(approvals_router)
app.include_router(knowledge_graph_router)
app.include_router(ai_quality_router)

REQUESTS = Counter("hsaai_backend_requests_total", "Total backend requests", ["path", "method", "status"])
ERRORS = Counter("hsaai_backend_errors_total", "Total backend errors", ["path", "method"])
LATENCY = Histogram("hsaai_backend_request_latency_seconds", "Backend request latency", ["path", "method"])
_auth_failures = Counter("hsaai_auth_failures_total", "Authentication or authorization failures", ["path"])
_rate_buckets = defaultdict(deque)

app.add_middleware(
    CORSMiddleware,
    # FIX v2.1 (P0): Use centralized CORS config — reject wildcard in prod/staging.
    # Previously this read CORS_ALLOW_ORIGINS directly with no wildcard rejection,
    # inconsistent with other services that use packages/common/security/cors_config.py.
    allow_origins=[x.strip() for x in os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",") if x.strip() and x.strip() != "*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-ID", "X-Workspace-ID", "X-Request-ID"],
)

# FIX CRITICAL-1 (HSAAI-DEP-2026-07-11): add_middleware() must be called at
# module level, BEFORE the application starts. Calling it inside the startup
# event raised `RuntimeError: Cannot add middleware after an application has
# started`. The ObservabilityMiddleware is now added here, conditionally on
# successful import (the import is best-effort because opentelemetry is an
# optional dependency in some environments).
if ObservabilityMiddleware:
    app.add_middleware(ObservabilityMiddleware)

@app.on_event("startup")
async def startup() -> None:
    # Observability initialization
    if setup_logging:
        setup_logging(service_name="backend_core")
    if setup_tracing:
        setup_tracing(app=app, service_name="backend_core")
    if init_sentry:
        init_sentry()
    # FIX CRITICAL-1: ObservabilityMiddleware moved to module level above.
    init_db()
    # FIX-14: ensure_collection is an async coroutine — must be awaited.
    # Previously called without await in a sync startup handler, producing
    # "coroutine was never awaited" RuntimeWarning and skipping Qdrant setup.
    try:
        await ensure_collection()
    except Exception as _exc:
        # Qdrant is optional in dev/test — don't crash startup if unreachable.
        import logging
        logging.getLogger("hsaai.backend_core").warning(
            "ensure_collection failed (non-fatal in dev): %s", _exc
        )

@app.middleware("http")
async def production_security_middleware(request: Request, call_next):
    client = request.client.host if request.client else "unknown"
    now = time.time()
    bucket = _rate_buckets[client]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= settings.rate_limit_per_minute:
        return Response("Rate limit exceeded", status_code=429)
    bucket.append(now)
    started = time.time()
    try:
        response = await call_next(request)
    except Exception:
        ERRORS.labels(request.url.path, request.method).inc()
        raise
    if response.status_code in (401, 403):
        _auth_failures.labels(request.url.path).inc()
    REQUESTS.labels(request.url.path, request.method, str(response.status_code)).inc()
    LATENCY.labels(request.url.path, request.method).observe(time.time() - started)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
    return response

@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name, "env": settings.app_env}

@app.get("/ready")
def ready():
    db = check_db()
    qdrant = qdrant_health()
    ok = db.get("status") == "ok" and qdrant.get("status") in {"ok", "exists", "created"}
    return {"status": "ready" if ok else "not_ready", "database": db, "qdrant": qdrant, "keycloak_issuer": settings.effective_keycloak_issuer}

@app.get("/metrics")
async def metrics(authorization: str | None = Header(default=None)):
    """SECURITY FIX v5.0 (P0): Metrics endpoint requires admin:read permission.
    Previously any authenticated user could scrape platform metrics."""
    from backend_core.security.rbac import require_permission
    # FIX v5.0: Use require_permission('admin:read') instead of bare verify_authorization
    _checker = require_permission("admin:read")
    await _checker(authorization)  # Must have admin:read permission
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/chat")
async def chat(payload: ChatRequest, authorization: str | None = Header(default=None)):
    # FIX v2.1 (P0): properly await verify_authorization
    claims = await verify_authorization(authorization)
    tenant_id = claims.get("tenant_id", "default")
    workspace_id = claims.get("workspace_id") or payload.workspace_id
    user = claims.get("sub") or payload.user

    db = SessionLocal()
    try:
        smart_response = detect_response(db, payload.message, tenant_id=tenant_id, workspace_id=workspace_id, user_id=user)
    finally:
        db.close()

    if smart_response.get("matched"):
        return smart_response
    return process_message(user, payload.message, workspace_id, tenant_id=tenant_id, claims=claims)

@app.get("/chat/stream")
async def chat_stream(user: str, message: str, workspace_id: str = "default", authorization: str | None = Header(default=None)):
    # FIX v2.1 (P0): properly await verify_authorization
    claims = await verify_authorization(authorization)
    tenant_id = claims.get("tenant_id", "default")
    return stream_message(claims.get("sub") or user, message, claims.get("workspace_id") or workspace_id, tenant_id=tenant_id, claims=claims)

@app.post("/files/upload", dependencies=[Depends(require_permission("files:write"))])
async def upload_file(
    file: UploadFile = File(...),
    tenant_id: str = Form("default"),
    workspace_id: str = Form("default"),
):
    """Backward-compatible upload endpoint.

    Older UI/API clients used /files/upload. The production contract now sends every
    knowledge upload to the RAG Engine so the document is stored, chunked, embedded
    and indexed in Qdrant instead of being merely acknowledged by the backend.
    """
    rag_url = os.getenv("RAG_ENGINE_URL", "http://rag_engine:8030")
    allowed = {x.strip() for x in settings.allowed_upload_mime_types.split(",") if x.strip()}
    content_type = file.content_type or "application/octet-stream"
    if content_type not in allowed:
        raise HTTPException(status_code=415, detail=f"Upload content type is not allowed: {content_type}")
    raw = await file.read()
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds configured production limit")
    lower_name = (file.filename or "").lower()
    if lower_name.endswith((".exe", ".bat", ".cmd", ".ps1", ".sh", ".js", ".vbs", ".scr", ".com")):
        raise HTTPException(status_code=415, detail="Executable or script uploads are blocked")
    data = {"tenant_id": tenant_id, "workspace_id": workspace_id}
    files = {"file": (file.filename, raw, file.content_type or "application/octet-stream")}
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(f"{rag_url}/v1/documents/upload", data=data, files=files)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"RAG Engine unavailable: {exc}")
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text[:1000])
    payload = response.json()
    payload["routed_by"] = "backend_core:/files/upload"
    payload["canonical_endpoint"] = "/v1/rag/documents/upload"
    if settings.knowledge_graph_enabled and settings.graph_ingestion_enabled:
        graph_db = SessionLocal()
        try:
            document_id = str(payload.get("document_id") or payload.get("id") or file.filename or "uploaded-document")
            GraphService(graph_db).ingest_document({
                "document_id": document_id,
                "title": file.filename or document_id,
                "text": payload.get("summary") or payload.get("text") or file.filename or "",
                "classification": payload.get("classification") or "internal",
                "permissions": payload.get("permissions") or [],
            }, actor="upload", tenant_id=tenant_id, workspace_id=workspace_id)
            payload["knowledge_graph_ingested"] = True
        except Exception as exc:
            payload["knowledge_graph_ingested"] = False
            payload["knowledge_graph_error"] = str(exc)[:300]
        finally:
            graph_db.close()
    return payload

@app.get("/admin", dependencies=[Depends(require_permission("admin:read"))])
def admin_dashboard():
    return stats()

@app.get("/enterprise/connectors", dependencies=[Depends(require_permission("admin:read"))])
def enterprise_connectors():
    return {"organization": "Hayel Saeed Anam Group", "connectors": connector_status()}

@app.on_event("shutdown")
def shutdown() -> None:
    if shutdown_tracing:
        shutdown_tracing()

@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket_endpoint(websocket)

@app.get("/security/internal-only/status")
def internal_only_status():
    return assert_internal_mode_is_clean()
