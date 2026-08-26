import os, httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/v1/llm", tags=["local-llm"])
LLM_URL = os.getenv("LLM_GATEWAY_URL", "http://llm_gateway:8090")

class GeneratePayload(BaseModel):
    prompt: str
    system: str = "You are HSAAI enterprise assistant."
    model: str | None = None
    workspace_id: str = "default"
    tenant_id: str = "default"
    temperature: float = 0.2
    max_tokens: int = 1024

@router.get("/models")
async def models():
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{LLM_URL}/v1/models")
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return r.json()

@router.post("/route")
async def route_model(payload: GeneratePayload):
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{LLM_URL}/v1/models/route", json=payload.model_dump())
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return r.json()

@router.post("/generate")
async def generate(payload: GeneratePayload):
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{LLM_URL}/v1/generate", json=payload.model_dump())
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return r.json()

@router.post("/stream")
async def stream(payload: GeneratePayload):
    async def relay():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{LLM_URL}/v1/stream", json={**payload.model_dump(), "stream": True}) as r:
                async for chunk in r.aiter_bytes():
                    yield chunk
    return StreamingResponse(relay(), media_type="text/event-stream")
