import asyncio
import os
import time
from typing import Any

import httpx
from fastapi.responses import StreamingResponse

from backend_core.rag.search import search_docs
from backend_core.memory.store import save_message, get_history
from backend_core.chat.router import route_agent
from backend_core.intent_detection.service import detect_intent, intent_to_agent
from backend_core.department_agents.service import resolve_department_agent, record_agent_run
from backend_core.db.database import SessionLocal
from backend_core.security.audit import audit
from backend_core.rag.citation_policy import require_citations
from backend_core.finops.service import log_llm_usage

AI_ORCHESTRATOR_URL = os.getenv("AI_ORCHESTRATOR_URL", "http://ai_orchestrator:8020")
RAG_ENGINE_URL = os.getenv("RAG_ENGINE_URL", "http://rag_engine:8030")
CHAT_USE_ORCHESTRATOR = os.getenv("CHAT_USE_ORCHESTRATOR", "true").lower() == "true"

AGENT_PREFIX = {
    "finance": "Finance Agent",
    "hr": "HR Agent",
    "executive": "Executive Agent",
    "rag": "Knowledge Agent",
    "knowledge": "Knowledge Agent",
    "it": "IT Support Agent",
    "procurement": "Procurement Agent",
    "legal": "Legal Agent",
    "operations": "Operations Agent",
    "general": "HSAAI Enterprise Assistant",
}

async def _search_rag_engine(message: str, tenant_id: str, workspace_id: str) -> list[dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{RAG_ENGINE_URL}/v1/search",
                json={"query": message, "tenant_id": tenant_id, "workspace_id": workspace_id, "top_k": 5},
            )
        if response.status_code >= 400:
            return []
        return response.json().get("results", []) or []
    except Exception:
        return []

def _build_context(rag_results: list[dict[str, Any]], legacy_results: list[str]) -> str:
    blocks: list[str] = []
    for idx, hit in enumerate(rag_results, start=1):
        filename = hit.get("filename", "unknown")
        chunk = hit.get("chunk_index", 0)
        text = hit.get("text", "")
        blocks.append(f"[source:{idx} file={filename} chunk={chunk}] {text}")
    for idx, text in enumerate(legacy_results, start=len(blocks) + 1):
        blocks.append(f"[source:{idx} file=legacy-memory chunk=0] {text}")
    return "\n\n".join(blocks[:6])

async def _call_orchestrator(message: str, agent: str, tenant_id: str, workspace_id: str, context: str, task: str | None = None, system_prompt: str | None = None, knowledge_scopes: list[str] | None = None) -> tuple[str, dict[str, Any]]:
    if not CHAT_USE_ORCHESTRATOR:
        return "", {}
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{AI_ORCHESTRATOR_URL}/orchestrate",
                json={
                    "message": message,
                    "tenant_id": tenant_id,
                    "workspace_id": workspace_id,
                    "preferred_agent": agent if agent != "rag" else "document",
                    "task": task,
                    "context": context,
                    "system_prompt": system_prompt,
                    "knowledge_scopes": knowledge_scopes or [],
                },
            )
        if response.status_code >= 400:
            return "", {"orchestrator_error": response.text[:300]}
        data = response.json()
        return data.get("response", ""), data
    except Exception as exc:
        return "", {"orchestrator_error": str(exc)}

def process_message(user: str, message: str, workspace_id: str = "default", tenant_id: str = "default", claims: dict[str, Any] | None = None) -> dict:
    started = time.time()
    # FIX (runtime): detect_intent signature is (query, tenant_id, workspace_id)
    # and returns a dict. Was called with one arg and accessed as attribute.
    intent_result = detect_intent(message, tenant_id=tenant_id, workspace_id=workspace_id)
    intent_key = intent_result.get("intent", "general_query") if isinstance(intent_result, dict) else "general_query"
    legacy_agent = intent_to_agent(intent_key) if intent_key != "general" else route_agent(message)
    claims = claims or {"sub": user, "roles": ["ai_user"], "tenant_id": tenant_id, "workspace_id": workspace_id, "department": workspace_id}

    db = SessionLocal()
    try:
        resolved = resolve_department_agent(message, claims, db, tenant_id=tenant_id, workspace_id=workspace_id)
    finally:
        db.close()
    agent = resolved.key if resolved.key != "general" else legacy_agent
    agent_name = resolved.name if resolved.key != "general" else AGENT_PREFIX.get(agent, "HSAAI Enterprise Assistant")

    save_message(user, "user", message, workspace_id, agent)

    legacy_rag = search_docs(message)
    rag_results = _search_rag_engine(message, tenant_id, workspace_id)
    context = _build_context(rag_results, legacy_rag)
    if resolved.knowledge_scopes:
        context = f"[agent_knowledge_scopes={','.join(resolved.knowledge_scopes)}]\n{context}".strip()
    history = get_history(user, workspace_id, limit=8)

    response, orchestration = _call_orchestrator(message, agent, tenant_id, workspace_id, context, task=intent_result.intent, system_prompt=resolved.system_prompt, knowledge_scopes=resolved.knowledge_scopes)
    if not response:
        response = f"{agent_name}: تم استلام طلبك وتحليله داخل مساحة العمل {workspace_id}."
        if context:
            response += f"\nتم العثور على {len(rag_results) + len(legacy_rag)} نتيجة معرفية مرتبطة بطلبك."
        response += f"\nعدد الرسائل في السياق الحالي: {len(history)}."

    sources = [{k: hit.get(k) for k in ["doc_id", "filename", "chunk_index", "score"]} for hit in rag_results]
    if sources:
        source_lines = "\n".join([f"[{i + 1}] {s.get('filename')}#chunk-{s.get('chunk_index')}" for i, s in enumerate(sources)])
        response = f"{response}\n\nالمصادر:\n{source_lines}"
        response = require_citations(response, sources=sources)

    elapsed_ms = int((time.time() - started) * 1000)
    token_usage = {"input_chars": len(message) + len(context), "output_chars": len(response), "elapsed_ms": elapsed_ms}

    save_message(user, "assistant", response, workspace_id, agent)
    audit(user, "chat.message", f"agent:{agent};tokens:{token_usage}", workspace_id)
    db = SessionLocal()
    try:
        record_agent_run(db, agent=resolved, actor=user, message=message, tenant_id=tenant_id, workspace_id=workspace_id, success=True, latency_ms=elapsed_ms)
        usage = log_llm_usage(db, user_id=user, department=claims.get("department", workspace_id), input_text=message + "\n" + context, output_text=response, operation_type="chat", agent=agent, workspace_id=workspace_id, tenant_id=tenant_id, project=workspace_id)
        token_usage.update({"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens, "estimated_cost": usage.estimated_cost})
    finally:
        db.close()
    return {
        "response": response,
        "agent": agent,
        "agent_name": agent_name,
        "agent_department": resolved.department,
        "agent_reason": resolved.reason,
        "agent_score": resolved.score,
        "knowledge_scopes": resolved.knowledge_scopes,
        "intent": intent_result.intent,
        "intent_score": intent_result.score,
        "rag_found": len(rag_results) + len(legacy_rag),
        "sources": sources,
        "workspace_id": workspace_id,
        "tenant_id": tenant_id,
        "token_usage": token_usage,
        "orchestration": orchestration,
    }

async def _tokens(text: str):
    for token in text.split():
        yield f"data: {token}\n\n"
        await asyncio.sleep(0.02)
    yield "data: [DONE]\n\n"

def stream_message(user: str, message: str, workspace_id: str = "default", tenant_id: str = "default", claims: dict[str, Any] | None = None):
    result = process_message(user, message, workspace_id, tenant_id=tenant_id, claims=claims)
    return StreamingResponse(_tokens(result["response"]), media_type="text/event-stream")
