"""
HSAAI BFF (Backend for Frontend) — GraphQL Gateway (v1.0)
============================================================
Aggregates data from multiple microservices into a single GraphQL API
optimized for the Next.js frontend.
"""
import os
import logging
from datetime import datetime
from typing import Optional
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="HSAAI BFF",
    version="1.0.0",
    description="Backend for Frontend — GraphQL aggregation gateway",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get(
        "CORS_ALLOW_ORIGINS",
        "https://hsaai.internal,https://app.hsaai.internal"
    ).split(",") if o.strip() and o.strip() != "*"],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
    allow_credentials=True,
)

START_TIME = datetime.now()

# Service URLs
BACKEND_CORE_URL = os.environ.get("BACKEND_CORE_URL", "http://backend-core:8000")
RAG_SERVICE_URL = os.environ.get("RAG_SERVICE_URL", "http://rag-service:8030")
AGENT_RUNTIME_URL = os.environ.get("AGENT_RUNTIME_URL", "http://agent-runtime:8040")
WORKFLOW_ENGINE_URL = os.environ.get("WORKFLOW_ENGINE_URL", "http://workflow-engine:8070")
GOVERNANCE_SERVICE_URL = os.environ.get("GOVERNANCE_SERVICE_URL", "http://governance-service:8011")
AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://auth-service:8010")
LLM_GATEWAY_URL = os.environ.get("LLM_GATEWAY_URL", "http://llm-gateway:8090")


@app.get("/health")
async def health():
    """Check health of BFF and all upstream services."""
    upstream_status = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in [
            ("backend-core", BACKEND_CORE_URL),
            ("rag-service", RAG_SERVICE_URL),
            ("agent-runtime", AGENT_RUNTIME_URL),
            ("workflow-engine", WORKFLOW_ENGINE_URL),
            ("governance-service", GOVERNANCE_SERVICE_URL),
            ("auth-service", AUTH_SERVICE_URL),
            ("llm-gateway", LLM_GATEWAY_URL),
        ]:
            try:
                resp = await client.get(f"{url}/health")
                upstream_status[name] = "healthy" if resp.status_code == 200 else f"error:{resp.status_code}"
            except Exception as e:
                upstream_status[name] = f"unreachable:{str(e)[:50]}"

    all_healthy = all(v == "healthy" for v in upstream_status.values())
    return {
        "status": "ok" if all_healthy else "degraded",
        "service": "bff",
        "version": "1.0.0",
        "uptime_seconds": int((datetime.now() - START_TIME).total_seconds()),
        "upstream": upstream_status,
    }


@app.get("/")
async def root():
    return {
        "service": "HSAAI BFF",
        "version": "1.0.0",
        "endpoints": ["/health", "/v1/dashboard", "/v1/agents", "/v1/chat", "/docs"],
    }


@app.get("/v1/dashboard")
async def get_dashboard():
    """Aggregate dashboard data from multiple services."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{BACKEND_CORE_URL}/api/dashboard/stats")
            dashboard = resp.json() if resp.status_code == 200 else {}
        except Exception:
            dashboard = {}

    return {
        "dashboard": dashboard,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/v1/agents")
async def get_agents():
    """Get all agents from the agent runtime."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{BACKEND_CORE_URL}/api/agents")
            return resp.json() if resp.status_code == 200 else {"agents": []}
        except Exception:
            return {"agents": [], "error": "agent service unavailable"}


class ChatRequest(BaseModel):
    message: str
    agent: Optional[str] = "general"


@app.post("/v1/chat")
async def chat(request: ChatRequest):
    """Forward chat request to backend."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{BACKEND_CORE_URL}/api/chat",
                json={"message": request.message, "agent": request.agent}
            )
            return resp.json() if resp.status_code == 200 else {"error": "chat failed"}
        except Exception as e:
            return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8095, log_level="info")
