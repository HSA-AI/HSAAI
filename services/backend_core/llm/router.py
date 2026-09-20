"""Authenticated LLM proxy; preserve caller scope and stream failure status."""
import os
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from backend_core.security.rbac import get_current_claims

router = APIRouter(prefix="/v1/llm", tags=["local-llm"])
LLM_URL = os.getenv("LLM_GATEWAY_URL", "http://llm-gateway:8090")

class GeneratePayload(BaseModel):
    prompt: str = Field(min_length=1, max_length=100000)
    system: str = "You are HSAAI enterprise assistant."
    model: str | None = None
    workspace_id: str = "default"
    tenant_id: str = "default"
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=1024, ge=1, le=32768)

async def proxy(path, authorization, payload=None):
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.request("POST" if payload is not None else "GET", f"{LLM_URL}{path}",
                                            json=payload, headers={"Authorization": authorization})
        if response.status_code >= 400:
            raise HTTPException(response.status_code, "LLM request failed")
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "LLM service unavailable") from exc

def scoped(payload, claims):
    return {**payload.model_dump(), "tenant_id": claims["tenant_id"], "workspace_id": claims["workspace_id"]}

@router.get("/models")
async def models(authorization: str = Header(), claims: dict = Depends(get_current_claims)):
    return await proxy("/v1/models", authorization)

@router.post("/route")
async def route_model(payload: GeneratePayload, authorization: str = Header(), claims: dict = Depends(get_current_claims)):
    return await proxy("/v1/models/route", authorization, scoped(payload, claims))

@router.post("/generate")
async def generate(payload: GeneratePayload, authorization: str = Header(), claims: dict = Depends(get_current_claims)):
    return await proxy("/v1/generate", authorization, scoped(payload, claims))

@router.post("/stream")
async def stream(payload: GeneratePayload, authorization: str = Header(), claims: dict = Depends(get_current_claims)):
    client = httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10))
    try:
        request = client.build_request("POST", f"{LLM_URL}/v1/stream", json={**scoped(payload, claims), "stream": True}, headers={"Authorization": authorization})
        response = await client.send(request, stream=True)
        if response.status_code >= 400:
            await response.aclose()
            raise HTTPException(response.status_code, "LLM stream unavailable")
    except Exception:
        await client.aclose()
        raise
    async def relay():
        try:
            async for chunk in response.aiter_bytes():
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()
    return StreamingResponse(relay(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
