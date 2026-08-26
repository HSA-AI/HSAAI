import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(
    title="HSAAI AI Orchestrator Compatibility Service",
    version="1.0.0",
)


MULTI_AGENTS_URL = os.getenv(
    "MULTI_AGENTS_URL",
    "http://multi_agents:8040",
).rstrip("/")


class OrchestrateRequest(BaseModel):
    message: str
    tenant_id: str = "default"
    workspace_id: str = "default"

    preferred_agent: str | None = None
    task: str | None = None

    context: str = ""
    system_prompt: str | None = None

    knowledge_scopes: list[str] = Field(default_factory=list)

    user_id: str | None = None
    claims: dict[str, Any] = Field(default_factory=dict)

    metadata: dict[str, Any] = Field(default_factory=dict)


def build_multi_agents_payload(
    request: OrchestrateRequest,
) -> dict[str, Any]:
    """
    Keep the adapter deliberately permissive.

    multi_agents implementations can evolve without requiring
    backend_core to know the internal schema.
    """

    return {
        "message": request.message,
        "tenant_id": request.tenant_id,
        "workspace_id": request.workspace_id,
        "preferred_agent": request.preferred_agent,
        "agent": request.preferred_agent,
        "task": request.task,
        "context": request.context,
        "system_prompt": request.system_prompt,
        "knowledge_scopes": request.knowledge_scopes,
        "user_id": request.user_id,
        "claims": request.claims,
        "metadata": request.metadata,
    }


def normalize_response(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        response = (
            data.get("response")
            or data.get("answer")
            or data.get("output")
            or data.get("result")
            or ""
        )

        result = dict(data)

        if response and "response" not in result:
            result["response"] = response

        return result

    if isinstance(data, str):
        return {
            "response": data,
        }

    return {
        "response": str(data),
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    multi_agents_status = "unknown"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{MULTI_AGENTS_URL}/health")

            if r.status_code < 400:
                multi_agents_status = "healthy"
            else:
                multi_agents_status = "unhealthy"

    except Exception:
        multi_agents_status = "unreachable"

    return {
        "status": "ok",
        "service": "ai_orchestrator",
        "multi_agents_url": MULTI_AGENTS_URL,
        "multi_agents_status": multi_agents_status,
    }


@app.get("/ready")
async def ready() -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{MULTI_AGENTS_URL}/health")

        if r.status_code >= 400:
            raise HTTPException(
                status_code=503,
                detail="multi_agents is unhealthy",
            )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"multi_agents unavailable: {exc}",
        )

    return {
        "status": "ready",
        "service": "ai_orchestrator",
    }


@app.post("/orchestrate")
async def orchestrate(request: OrchestrateRequest) -> dict[str, Any]:
    payload = build_multi_agents_payload(request)

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{MULTI_AGENTS_URL}/v1/run",
                json=payload,
            )

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="multi_agents request timed out",
        )

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"multi_agents unavailable: {exc}",
        )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.text[:1000],
        )

    try:
        data = response.json()
    except Exception:
        data = response.text

    result = normalize_response(data)

    result.setdefault(
        "orchestrator",
        "ai_orchestrator",
    )

    result.setdefault(
        "multi_agents_url",
        MULTI_AGENTS_URL,
    )

    return result
