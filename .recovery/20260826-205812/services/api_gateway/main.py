import os
import sys
import time
import socket
import ipaddress
from urllib.parse import urlparse
from collections import defaultdict, deque

import httpx
from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# FIX FIX-MEDIUM-QUALITY (Issue 4): import canonical SSRF guard from common.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
try:
    from common.security.ssrf_guard import is_private_url as _is_private_url  # noqa: F401
    _SSRF_GUARD_AVAILABLE = True
except ImportError:
    _SSRF_GUARD_AVAILABLE = False

app = FastAPI(title="HSAAI API Gateway", version="4.0.0")

INTERNAL_ONLY_MODE = os.getenv("INTERNAL_ONLY_MODE", "true").lower() == "true"
ALLOW_EXTERNAL_APIS = os.getenv("ALLOW_EXTERNAL_APIS", "false").lower() == "true"
STRICT_EGRESS_DENY = os.getenv("STRICT_EGRESS_DENY", "true").lower() == "true"
BLOCKED_EXTERNAL_SECRET_KEYS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "MISTRAL_API_KEY", "COHERE_API_KEY", "PINECONE_API_KEY")
INTERNAL_SERVICE_HOSTS = {
    "backend", "auth_service", "ai_orchestrator", "rag_engine", "analytics", "llm_gateway",
    "postgres", "redis", "qdrant", "elasticsearch", "keycloak", "local_llm",
    "prometheus", "grafana", "otel-collector", "localhost", "127.0.0.1", "api_gateway"
}
PRIVATE_CIDRS = [
    ipaddress.ip_network(os.getenv("PRIVATE_NETWORK_CIDR", "172.28.0.0/16"), strict=False),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
]

def _is_private_url_fallback(url: str) -> bool:
    # NOTE: kept as fallback only — used if common.security.ssrf_guard import failed.
    host = urlparse(url).hostname
    if not host:
        return True
    if host in INTERNAL_SERVICE_HOSTS or host.endswith(".svc") or host.endswith(".svc.cluster.local"):
        return True
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(host))
        return any(ip in net for net in PRIVATE_CIDRS)
    except Exception:
        return False

if not _SSRF_GUARD_AVAILABLE:
    _is_private_url = _is_private_url_fallback  # type: ignore[assignment]

def assert_internal_only_config() -> dict:
    leaked = [k for k in BLOCKED_EXTERNAL_SECRET_KEYS if os.getenv(k)]
    upstreams = {
        "BACKEND_URL": os.getenv("BACKEND_URL", "http://backend:8000"),
        "AI_ORCHESTRATOR_URL": os.getenv("AI_ORCHESTRATOR_URL", "http://ai_orchestrator:8020"),
        "RAG_ENGINE_URL": os.getenv("RAG_ENGINE_URL", "http://rag_engine:8030"),
        "AUTH_SERVICE_URL": os.getenv("AUTH_SERVICE_URL", "http://auth_service:8010"),
        "ANALYTICS_URL": os.getenv("ANALYTICS_URL", "http://analytics:8070"),
    }
    external = {k: v for k, v in upstreams.items() if not _is_private_url(v)}
    if INTERNAL_ONLY_MODE and not ALLOW_EXTERNAL_APIS and leaked:
        raise RuntimeError(f"External AI/API secrets are forbidden in HSAAI internal-only mode: {', '.join(leaked)}")
    if INTERNAL_ONLY_MODE and STRICT_EGRESS_DENY and external:
        raise RuntimeError(f"External upstream URLs are forbidden in HSAAI internal-only mode: {external}")
    return {"internal_only_mode": INTERNAL_ONLY_MODE, "allow_external_apis": ALLOW_EXTERNAL_APIS, "strict_egress_deny": STRICT_EGRESS_DENY, "blocked_keys_present": leaked, "upstreams": upstreams}

def guard_upstream_url(url: str) -> None:
    if INTERNAL_ONLY_MODE and STRICT_EGRESS_DENY and not ALLOW_EXTERNAL_APIS and not _is_private_url(url):
        raise HTTPException(403, f"Outbound URL blocked by HSAAI internal-only policy: {url}")


CORS_ALLOW_ORIGINS = [x.strip() for x in os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-ID", "X-Workspace-ID", "X-Request-ID"],
)

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
AI_URL = os.getenv("AI_ORCHESTRATOR_URL", "http://ai_orchestrator:8020")
RAG_URL = os.getenv("RAG_ENGINE_URL", "http://rag_engine:8030")
AUTH_URL = os.getenv("AUTH_SERVICE_URL", "http://auth_service:8010")
ANALYTICS_URL = os.getenv("ANALYTICS_URL", "http://analytics:8070")
AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "true").lower() == "true"
# SECURITY FIX: ALLOW_DEV_AUTH removed. No dev bypass permitted.
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))
# SECURITY FIX v2.0: Removed /docs, /openapi.json, /redoc from PUBLIC_PATHS.
# API surface should not be browsable by unauthenticated users. Admins can use port-forwarding.
PUBLIC_PATHS = {"/health", "/ready"}
_BUCKETS: dict[str, deque[float]] = defaultdict(deque)

async def enforce_rate_limit(request: Request):
    # SECURITY FIX: Rate limit by client IP, not full auth token (token in memory = leak risk)
    key = request.client.host if request.client else "unknown"
    now = time.time()
    bucket = _BUCKETS[key]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(429, "Rate limit exceeded")
    bucket.append(now)

async def verify_session(request: Request) -> dict:
    await enforce_rate_limit(request)
    if request.url.path in PUBLIC_PATHS:
        return {"active": True, "sub": "anonymous", "roles": ["viewer"], "tenant_id": "default", "workspace_id": "default"}
    # SECURITY FIX: AUTH_REQUIRED is always enforced. No anonymous access to protected endpoints.
    authorization = request.headers.get("authorization")
    if not authorization:
        # SECURITY FIX: Removed ALLOW_DEV_AUTH bypass
        raise HTTPException(401, "Missing bearer token")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{AUTH_URL}/v1/token/verify", headers={"Authorization": authorization})
    except httpx.HTTPError as exc:
        raise HTTPException(503, f"Auth service unavailable: {exc}")
    if r.status_code >= 400:
        raise HTTPException(401, "Invalid or expired bearer token")
    claims = r.json()
    # SECURITY FIX v2.0: Tenant ID MUST come from JWT only — NEVER from client headers.
    # Previous code allowed X-Tenant-ID header override → tenant isolation bypass.
    if "tenant_id" not in claims:
        claims["tenant_id"] = "default"
    if "workspace_id" not in claims:
        claims["workspace_id"] = "default"
    return claims

def forward_headers(request: Request, claims: dict | None = None) -> dict:
    headers = {k: v for k, v in request.headers.items() if k.lower() in {"authorization", "content-type", "x-request-id"}}
    if claims:
        headers["X-Tenant-ID"] = str(claims.get("tenant_id", "default"))
        headers["X-Workspace-ID"] = str(claims.get("workspace_id", "default"))
        headers["X-User-ID"] = str(claims.get("sub", "unknown"))
    return headers

async def forward_json(method: str, url: str, payload=None, headers=None, timeout=60):
    guard_upstream_url(url)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.request(method, url, json=payload, headers=headers)
        return JSONResponse(status_code=r.status_code, content=r.json())
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Upstream service error: {exc}")
    except ValueError:
        raise HTTPException(502, "Upstream returned invalid JSON")

@app.get("/health")
def health():
    return {"status": "ok", "service": "api_gateway", "version": "10.5.0-internal-only", "auth_required": AUTH_REQUIRED, "internal_only": assert_internal_only_config(), "rag_contract": "/v1/documents/upload"}

@app.post("/v1/chat")
async def chat(request: Request, claims: dict = Depends(verify_session)):
    payload = await request.json()
    payload["workspace_id"] = claims.get("workspace_id") or payload.get("workspace_id", "default")
    payload["user"] = claims.get("sub") or payload.get("user", "current-user")
    return await forward_json("POST", f"{BACKEND_URL}/chat", payload=payload, headers=forward_headers(request, claims), timeout=120)

@app.post("/v1/llm/generate")
async def llm_generate_alias(request: Request, claims: dict = Depends(verify_session)):
    payload = await request.json()
    message = payload.get("prompt") or payload.get("message") or ""
    return await forward_json("POST", f"{AI_URL}/orchestrate", payload={"message": message, "tenant_id": claims.get("tenant_id", "default"), "workspace_id": claims.get("workspace_id", "default")}, headers=forward_headers(request, claims), timeout=120)

@app.get("/v1/dashboard")
async def dashboard(request: Request, claims: dict = Depends(verify_session)):
    return await forward_json("GET", f"{BACKEND_URL}/admin", headers=forward_headers(request, claims), timeout=30)

@app.post("/v1/rag/documents/upload")
async def upload_rag_document(request: Request, file: UploadFile = File(...), tenant_id: str = Form("default"), workspace_id: str = Form("default"), claims: dict = Depends(verify_session)):
    tenant_id = claims.get("tenant_id") or tenant_id
    workspace_id = claims.get("workspace_id") or workspace_id
    content = await file.read()
    guard_upstream_url(f"{RAG_URL}/v1/documents/upload")
    async with httpx.AsyncClient(timeout=180) as client:
        files = {"file": (file.filename, content, file.content_type or "application/octet-stream")}
        data = {"tenant_id": tenant_id, "workspace_id": workspace_id}
        r = await client.post(f"{RAG_URL}/v1/documents/upload", files=files, data=data, headers=forward_headers(request, claims))
    try:
        content_json = r.json()
    except ValueError:
        raise HTTPException(502, "RAG Engine returned invalid JSON")
    return JSONResponse(status_code=r.status_code, content=content_json)

@app.post("/v1/rag/search")
async def rag_search(request: Request, claims: dict = Depends(verify_session)):
    payload = await request.json()
    payload["tenant_id"] = claims.get("tenant_id") or payload.get("tenant_id", "default")
    payload["workspace_id"] = claims.get("workspace_id") or payload.get("workspace_id", "default")
    return await forward_json("POST", f"{RAG_URL}/v1/search", payload=payload, headers=forward_headers(request, claims), timeout=60)

@app.post("/v1/rag/answer")
async def rag_answer(request: Request, claims: dict = Depends(verify_session)):
    payload = await request.json()
    payload["tenant_id"] = claims.get("tenant_id") or payload.get("tenant_id", "default")
    payload["workspace_id"] = claims.get("workspace_id") or payload.get("workspace_id", "default")
    return await forward_json("POST", f"{RAG_URL}/v1/answer", payload=payload, headers=forward_headers(request, claims), timeout=90)


@app.post("/v1/rag/highlight")
async def rag_highlight(request: Request, claims: dict = Depends(verify_session)):
    payload = await request.json()
    payload["tenant_id"] = claims.get("tenant_id") or payload.get("tenant_id", "default")
    payload["workspace_id"] = claims.get("workspace_id") or payload.get("workspace_id", "default")
    return await forward_json("POST", f"{RAG_URL}/v1/highlight", payload=payload, headers=forward_headers(request, claims), timeout=60)

@app.post("/v1/rag/answer/stream")
async def rag_answer_stream(request: Request, claims: dict = Depends(verify_session)):
    from fastapi.responses import StreamingResponse
    payload = await request.json()
    payload["tenant_id"] = claims.get("tenant_id") or payload.get("tenant_id", "default")
    payload["workspace_id"] = claims.get("workspace_id") or payload.get("workspace_id", "default")
    url = f"{RAG_URL}/v1/answer/stream"
    guard_upstream_url(url)
    async def event_proxy():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", url, json=payload, headers=forward_headers(request, claims)) as upstream:
                async for chunk in upstream.aiter_bytes():
                    yield chunk
    return StreamingResponse(event_proxy(), media_type="text/event-stream")

@app.post("/v1/rag/ingest")
async def ingest_alias(request: Request, file: UploadFile = File(...), tenant_id: str = Form("default"), workspace_id: str = Form("default"), claims: dict = Depends(verify_session)):
    return await upload_rag_document(request=request, file=file, tenant_id=tenant_id, workspace_id=workspace_id, claims=claims)

@app.get("/v1/security/internal-only/status")
async def internal_status(request: Request, claims: dict = Depends(verify_session)):
    return await forward_json("GET", f"{BACKEND_URL}/security/internal-only/status", headers=forward_headers(request, claims), timeout=20)

@app.get("/v1/enterprise/connectors")
async def enterprise_connectors(request: Request, claims: dict = Depends(verify_session)):
    return await forward_json("GET", f"{BACKEND_URL}/enterprise/connectors", headers=forward_headers(request, claims), timeout=30)


# Phase 5: Enterprise AI Operations Platform proxy routes
async def phase5_ops_proxy(request: Request, suffix: str, claims: dict):
    method = request.method
    url = f"{BACKEND_URL}/v1/ops/{suffix}"
    payload = None
    if method in {"POST", "PUT", "PATCH"}:
        payload = await request.json()
    return await forward_json(method, url, payload=payload, headers=forward_headers(request, claims), timeout=120)

@app.get("/v1/ops/agents")
async def ops_agents(request: Request, claims: dict = Depends(verify_session)):
    return await phase5_ops_proxy(request, "agents", claims)

@app.post("/v1/ops/agents/run")
async def ops_agents_run(request: Request, claims: dict = Depends(verify_session)):
    return await phase5_ops_proxy(request, "agents/run", claims)

@app.post("/v1/ops/workflows/run")
async def ops_workflows_run(request: Request, claims: dict = Depends(verify_session)):
    return await phase5_ops_proxy(request, "workflows/run", claims)

@app.post("/v1/ops/models/route")
async def ops_models_route(request: Request, claims: dict = Depends(verify_session)):
    return await phase5_ops_proxy(request, "models/route", claims)

@app.post("/v1/ops/search")
async def ops_enterprise_search(request: Request, claims: dict = Depends(verify_session)):
    return await phase5_ops_proxy(request, "search", claims)

@app.get("/v1/ops/observability/metrics")
async def ops_observability_metrics(request: Request, claims: dict = Depends(verify_session)):
    return await phase5_ops_proxy(request, "observability/metrics", claims)

@app.get("/v1/ops/observability/events")
async def ops_observability_events(request: Request, limit: int = 100, claims: dict = Depends(verify_session)):
    return await phase5_ops_proxy(request, f"observability/events?limit={limit}", claims)
