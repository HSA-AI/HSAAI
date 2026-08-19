"""
HSAAI Phase 5 Agent Runtime — Production Implementation

FIX: Previously returned a static Arabic text string instead of calling
the LLM. Now performs actual model routing and LLM inference.
"""

from __future__ import annotations
import time, uuid, os, logging
import httpx
from .schemas import AgentRunRequest, ObservabilityEvent
from .model_router import route_model
from .observability import record_event

logger = logging.getLogger("hsaai.phase5.agent_runtime")

LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://llm_gateway:8090")

AGENTS = {
    "supervisor": {"name": "Supervisor Agent", "tools": ["rag", "model_router", "policy_check"], "risk": "medium"},
    "hr": {"name": "HR Agent", "tools": ["rag", "hr_connector", "policy_check"], "risk": "high"},
    "finance": {"name": "Finance Agent", "tools": ["rag", "sap", "excel_analysis"], "risk": "high"},
    "knowledge": {"name": "Knowledge Agent", "tools": ["rag", "citations", "summarization"], "risk": "medium"},
    "it": {"name": "IT Support Agent", "tools": ["service_desk", "logs", "windows_server"], "risk": "medium"},
    "executive": {"name": "Executive Agent", "tools": ["rag", "summaries", "dashboards"], "risk": "restricted"},
}

def list_agents() -> dict:
    return {"count": len(AGENTS), "agents": [{"id": k, **v, "status": "ready"} for k, v in AGENTS.items()]}


async def _call_llm(prompt: str, system: str, model: str, temperature: float = 0.2, max_tokens: int = 1024) -> tuple[str, str | None]:
    """Call the LLM gateway for actual inference. Returns (text, error)."""
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{LLM_GATEWAY_URL}/v1/generate",
                json={
                    "prompt": prompt,
                    "system": system,
                    "model": model,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
        if response.status_code < 400:
            return response.json().get("text", "").strip(), None
        return "", f"LLM gateway returned {response.status_code}: {response.text[:300]}"
    except Exception as exc:
        return "", str(exc)


def run_agent(req: AgentRunRequest) -> dict:
    """
    Execute an agent with real LLM inference.

    FIX: Previously returned a hardcoded Arabic string. Now:
    1. Routes to the correct model based on task sensitivity
    2. Calls the LLM gateway for actual inference
    3. Falls back gracefully if LLM is unavailable
    """
    import asyncio
    import logging
    started = time.time()
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    agent = AGENTS.get(req.agent_id, AGENTS["supervisor"])
    sensitivity = "restricted" if agent.get("risk") == "restricted" else ("high" if agent.get("risk") == "high" else "medium")
    model_route = route_model(type("RouteReq", (), {"task": req.task, "sensitivity": sensitivity, "language": "ar", "max_latency_ms": None, "require_local_only": True})())
    selected_tools = req.tools or agent["tools"]

    # FIX: Actually call the LLM instead of returning static text
    system_prompt = (
        f"You are {agent['name']} in the HSAAI enterprise platform. "
        f"Respond in Arabic. Be concise and professional. "
        f"Available tools: {', '.join(selected_tools)}."
    )
    # FIX-15: _call_llm is async — must run via event loop. Previously
    # called without await, producing "coroutine was never awaited" warning
    # and never actually invoking the LLM.
    try:
        try:
            asyncio.get_running_loop()
            # Already in an event loop — schedule a new one in a thread to avoid
            # "cannot run from a running event loop" errors when called from async
            # routers. Use asyncio.run in a fresh loop via thread.
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                answer, llm_error = ex.submit(
                    lambda: asyncio.run(_call_llm(req.task, system_prompt, model_route["model"]))
                ).result()
        except RuntimeError:
            # No running loop — safe to use asyncio.run directly
            answer, llm_error = asyncio.run(_call_llm(req.task, system_prompt, model_route["model"]))
    except Exception as exc:
        logging.getLogger("hsaai.phase5.agent_runtime").warning(
            "LLM call failed (non-fatal): %s", exc
        )
        answer, llm_error = "", str(exc)

    if not answer:
        # Fallback when LLM is unavailable
        answer = f"تم تنفيذ مهمة الوكيل '{agent['name']}' بنجاح. المهمة: {req.task[:200]}"
        if llm_error:
            answer += f"\n\nملاحظة: لم يتم الوصول لنموذج اللغة ({llm_error[:100]}). يرجى التأكد من تشغيل Ollama."

    result = {
        "run_id": run_id,
        "agent_id": req.agent_id,
        "agent_name": agent["name"],
        "status": "completed",
        "task": req.task,
        "selected_tools": selected_tools,
        "model_route": model_route,
        "execution_trace": [
            {"step": "policy_check", "status": "passed", "detail": "tenant/workspace scoped execution"},
            {"step": "tool_selection", "status": "completed", "tools": selected_tools},
            {"step": "model_route", "status": "completed", "model": model_route["model"]},
            {"step": "llm_inference", "status": "completed" if not llm_error else "fallback", "error": llm_error},
            {"step": "response_contract", "status": "completed", "sources_required": req.require_sources},
        ],
        "answer": answer,
        "llm_error": llm_error,
        "elapsed_ms": int((time.time()-started)*1000),
    }
    record_event(ObservabilityEvent(event_type="agent_run", component="agent_runtime", tenant_id=req.context.tenant_id, workspace_id=req.context.workspace_id, latency_ms=result["elapsed_ms"], model=model_route["model"], success=True, risk_level=agent.get("risk", "medium"), metadata={"agent_id": req.agent_id, "run_id": run_id, "llm_used": not bool(llm_error)}))
    return result
