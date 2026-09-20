"""
HSAAI Workflow Engine — Release Candidate

FIX: Replaced the stub implementation that immediately marked workflows as
"completed" with a real execution engine that:
- Tracks workflow state in this process; durable storage remains a release blocker
- Executes steps sequentially with actual tool/agent calls
- Tracks state transitions properly
- Supports approval nodes with human-in-the-loop
- Records real execution history and metrics
"""

import os
import time
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Depends, Request, Query
# SECURITY FIX v2.0: Add shared service auth
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..', '..', 'packages'))
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
    _AUTH_AVAILABLE = True
except ImportError as _e:
    _AUTH_AVAILABLE = False
    _AUTH_LOAD_ERROR = str(_e)
    async def _auth_dep():  # type: ignore
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Authentication module unavailable. Service cannot accept requests.")

from pydantic import BaseModel, Field
from common.security.request_policy import verified_scope, authorization_context, outgoing_headers
from common.auth.service_auth import _extract_roles, _has_permission

APP_VERSION = "4.0.0"  # FIX B-09: aligned with VERSION file
BACKEND_CORE_URL = os.getenv("BACKEND_CORE_URL", "http://backend-core:8000")
RAG_ENGINE_URL = os.getenv("RAG_ENGINE_URL", "http://rag-service:8030")
LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://llm-gateway:8090")

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("hsaai.workflow_engine")

app = FastAPI(title="HSAAI Workflow Engine", version=APP_VERSION)

# Process-local state. Restart persistence and distributed coordination are not implemented.
RUNS: dict[str, dict[str, Any]] = {}
EXECUTION_HISTORY: list[dict[str, Any]] = []


class WorkflowStep(BaseModel):
    id: str
    type: str  # "rag" | "agent" | "approval" | "notification" | "llm" | "tool"
    name: str = ""
    config: dict[str, Any] = Field(default_factory=dict)


class WorkflowRequest(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    steps: list[str] | None = None
    structured_steps: list[WorkflowStep] | None = None
    workspace_id: str = "default"
    tenant_id: str = "default"
    payload: dict[str, Any] = Field(default_factory=dict)


class WorkflowStatusRequest(BaseModel):
    run_id: str


def _parse_steps(steps: list[str] | None, structured: list[WorkflowStep] | None) -> list[WorkflowStep]:
    """Parse step definitions from either string format or structured format."""
    if structured:
        return structured
    if steps:
        return [WorkflowStep(id=f"step-{i}", type="llm", name=s) for i, s in enumerate(steps)]
    return [WorkflowStep(id="default", type="llm", name="Default processing step")]


async def _execute_rag_step(step: WorkflowStep, context: dict[str, Any]) -> dict[str, Any]:
    """Execute a RAG retrieval step by calling the RAG engine."""
    query = step.config.get("query") or context.get("query", "")
    if not query:
        return {"step_id": step.id, "status": "skipped", "reason": "No query provided"}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{RAG_ENGINE_URL}/v1/search",
                headers=outgoing_headers(),
                json={
                    "query": query,
                    "tenant_id": context.get("tenant_id", "default"),
                    "workspace_id": context.get("workspace_id", "default"),
                    "top_k": step.config.get("top_k", 5),
                },
            )
        if response.status_code >= 400:
            return {"step_id": step.id, "status": "error", "error": f"RAG engine returned {response.status_code}"}
        data = response.json()
        return {"step_id": step.id, "status": "completed", "results_count": len(data.get("results", [])), "results": data.get("results", [])[:3]}
    except Exception as exc:
        logger.error("RAG step failed: %s", type(exc).__name__)
        return {"step_id": step.id, "status": "error", "error": "Upstream step failed"}


async def _execute_llm_step(step: WorkflowStep, context: dict[str, Any]) -> dict[str, Any]:
    """Execute an LLM generation step by calling the LLM gateway."""
    prompt = step.config.get("prompt") or step.name or context.get("query", "")
    system = step.config.get("system", "You are HSAAI, an enterprise AI assistant. Respond in Arabic.")
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{LLM_GATEWAY_URL}/v1/generate",
                headers=outgoing_headers(),
                json={
                    "prompt": prompt,
                    "system": system,
                    "model": step.config.get("model"),
                    "temperature": step.config.get("temperature", 0.2),
                    "max_tokens": step.config.get("max_tokens", 1024),
                    "tenant_id": context.get("tenant_id", "default"),
                    "workspace_id": context.get("workspace_id", "default"),
                },
            )
        if response.status_code >= 400:
            return {"step_id": step.id, "status": "error", "error": f"LLM gateway returned {response.status_code}"}
        data = response.json()
        return {"step_id": step.id, "status": "completed", "answer": data.get("text", ""), "model": data.get("model", ""), "elapsed_ms": data.get("elapsed_ms", 0)}
    except Exception as exc:
        logger.error("LLM step failed: %s", type(exc).__name__)
        return {"step_id": step.id, "status": "error", "error": "Upstream step failed"}


def _execute_approval_step(step: WorkflowStep, context: dict[str, Any]) -> dict[str, Any]:
    """Create an approval request for human-in-the-loop workflows."""
    return {
        "step_id": step.id,
        "status": "waiting_approval",
        "approver": step.config.get("approver", "admin"),
        "message": step.config.get("message", "Approval required for workflow step"),
        "timeout_seconds": step.config.get("timeout_seconds", 86400),
    }


async def _execute_agent_step(step: WorkflowStep, context: dict[str, Any]) -> dict[str, Any]:
    """Execute an agent step by calling the backend core agent runtime."""
    agent_id = step.config.get("agent_id", "supervisor")
    prompt = step.config.get("prompt") or context.get("query", "")
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{BACKEND_CORE_URL}/v1/agent-runtime/run",
                json={"agent_id": agent_id, "prompt": prompt, "session_id": context.get("session_id", "default")},
                headers=outgoing_headers(),
            )
        if response.status_code >= 400:
            return {"step_id": step.id, "status": "error", "error": f"Agent runtime returned {response.status_code}"}
        data = response.json()
        return {"step_id": step.id, "status": "completed", "agent_id": agent_id, "answer": data.get("answer", ""), "run_id": data.get("run_id", "")}
    except Exception as exc:
        logger.error("Agent step failed: %s", type(exc).__name__)
        return {"step_id": step.id, "status": "error", "error": "Upstream step failed"}


async def _execute_tool_step(step, context):
    """FIX v0.1 (P1): Add missing 'tool' step executor that calls
    packages.common.tool_registry.dispatch_tool."""
    tool_name = step.config.get("tool_name") or step.config.get("tool")
    tool_args = step.config.get("args", {}) or step.config.get("parameters", {})
    if not tool_name:
        return {"step_id": step.id, "status": "error", "error": "Missing 'tool_name' in step config"}
    try:
        # Import the shared tool registry
        import sys as _sys, os as _os
        _pkgs = _os.path.join(_os.path.dirname(__file__), '..', '..', 'packages')
        if _pkgs not in _sys.path:
            _sys.path.insert(0, _pkgs)
        from common.tool_registry import dispatch_tool  # type: ignore
        tool_context = {
            "tenant_id": context.get("tenant_id", "default"),
            "workspace_id": context.get("workspace_id", "default"),
            "user_id": context.get("user_id", "system"),
            "token": context.get("token", ""),
        }
        result = await dispatch_tool(tool_name, tool_args, tool_context)
        return {"step_id": step.id, "status": "completed", "tool": tool_name, "result": result}
    except ImportError:
        return {"step_id": step.id, "status": "skipped", "reason": "tool_registry not available"}
    except Exception as exc:
        logger.error("Tool step failed: %s", type(exc).__name__)
        return {"step_id": step.id, "status": "error", "error": "Upstream step failed"}


STEP_EXECUTORS = {
    "rag": _execute_rag_step,
    "llm": _execute_llm_step,
    "approval": _execute_approval_step,
    "agent": _execute_agent_step,
    "tool": _execute_tool_step,  # FIX v0.1 (P1): Add missing tool executor
}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "workflow_engine",
        "version": APP_VERSION,
        "active_runs": len([r for r in RUNS.values() if r.get("status") == "running"]),
        "total_completed": len([r for r in RUNS.values() if r.get("status") == "completed"]),
    }


async def _scoped_auth(request: Request, claims: dict = Depends(_auth_dep)):
    _scope(claims)
    token = authorization_context.set(request.headers.get("authorization", ""))
    try:
        yield claims
    finally:
        authorization_context.reset(token)


def _scope(claims):
    try:
        tenant, workspace = verified_scope(claims)
        user = claims.get("sub")
        if not isinstance(user, str) or not user.strip():
            raise ValueError("Verified subject required")
        return tenant, workspace, user
    except (ValueError, TypeError):
        raise HTTPException(status_code=403, detail="Verified tenant and workspace required")


def _permission(claims, permission):
    if not _has_permission(_extract_roles(claims), permission):
        raise HTTPException(status_code=403, detail="Permission denied")


def _record(run_id, claims):
    tenant, workspace, _ = _scope(claims)
    row = RUNS.get(run_id)
    if row is None or (row["tenant_id"], row["workspace_id"]) != (tenant, workspace):
        raise HTTPException(status_code=404, detail="Workflow not found")
    return row


def _history_record(row):
    item = {k: row.get(k) for k in (
        "run_id", "name", "status", "tenant_id", "workspace_id", "started_at",
        "completed_at", "steps_total", "steps_completed", "steps_failed",
    )}
    for i, previous in enumerate(EXECUTION_HISTORY):
        if previous["run_id"] == row["run_id"]:
            EXECUTION_HISTORY[i] = item
            return
    EXECUTION_HISTORY.append(item)


def _summary(row):
    return {k: row[k] for k in (
        "run_id", "status", "steps_total", "steps_completed", "steps_failed", "step_results",
    )}


async def _continue_run(row):
    context = dict(row["context"])
    context["token"] = outgoing_headers().get("Authorization", "").removeprefix("Bearer ")
    row["status"] = "running"
    for index in range(row["next_step"], len(row["steps"])):
        step = WorkflowStep.model_validate(row["steps"][index])
        executor = STEP_EXECUTORS.get(step.type)
        if executor is None:
            result = {"step_id": step.id, "status": "error", "error": "Unknown step type"}
        else:
            try:
                result = executor(step, context)
                if asyncio.iscoroutine(result):
                    result = await result
            except Exception as exc:
                logger.error("Workflow executor failed: %s", type(exc).__name__)
                result = {"step_id": step.id, "status": "error", "error": "Upstream step failed"}
        row["step_results"].append(result)
        row["next_step"] = index + 1
        status = result.get("status")
        if status == "completed":
            row["steps_completed"] += 1
            if "answer" in result:
                context["previous_answer"] = result["answer"]
            if "results" in result:
                context["rag_context"] = result["results"]
        elif status == "waiting_approval":
            row["status"] = "waiting_approval"
            break
        else:
            row["steps_failed"] += 1
            if step.config.get("fail_workflow_on_error", True):
                row["status"] = "failed"
                break
    context.pop("token", None)
    row["context"] = context
    if row["status"] == "running":
        row["status"] = "failed" if row["steps_failed"] else "completed"
    if row["status"] in {"completed", "failed"}:
        row["completed_at"] = datetime.now(timezone.utc).isoformat()
    _history_record(row)


@app.post("/workflows/run")
async def run(payload: WorkflowRequest, claims: dict = Depends(_scoped_auth)):
    tenant, workspace, user = _scope(claims)
    _permission(claims, "workflows:execute")
    steps = _parse_steps(payload.steps, payload.structured_steps)
    if len(steps) > 100 or len({s.id for s in steps}) != len(steps):
        raise HTTPException(status_code=422, detail="Use at most 100 steps with unique IDs")
    if len(RUNS) >= 10000:
        raise HTTPException(status_code=503, detail="Workflow storage capacity reached")
    run_id = str(uuid.uuid4())
    row = {
        "run_id": run_id, "name": payload.name, "status": "running",
        "tenant_id": tenant, "workspace_id": workspace, "requester": user,
        "steps": [s.model_dump() for s in steps], "next_step": 0,
        "steps_total": len(steps), "steps_completed": 0, "steps_failed": 0,
        "started_at": datetime.now(timezone.utc).isoformat(), "step_results": [],
        "context": {"tenant_id": tenant, "workspace_id": workspace, "user_id": user,
                    "query": payload.payload.get("query", ""),
                    "session_id": payload.payload.get("session_id", "default")},
    }
    RUNS[run_id] = row
    await _continue_run(row)
    return _summary(row)


# Declare the static route before the run_id route.
@app.get("/workflows/history")
def history(limit: int = Query(default=50, ge=1, le=200), claims: dict = Depends(_scoped_auth)):
    tenant, workspace, _ = _scope(claims)
    _permission(claims, "workflows:read")
    rows = [r for r in EXECUTION_HISTORY if (r["tenant_id"], r["workspace_id"]) == (tenant, workspace)]
    return {"items": list(reversed(rows[-limit:]))}


@app.get("/workflows/{run_id}")
def status(run_id: str, claims: dict = Depends(_scoped_auth)):
    _permission(claims, "workflows:read")
    row = _record(run_id, claims)
    return {k: v for k, v in row.items() if k not in {"context", "steps"}}


@app.post("/workflows/{run_id}/approve/{step_id}")
async def approve_step(run_id: str, step_id: str, claims: dict = Depends(_scoped_auth)):
    _permission(claims, "approvals:decide")
    row = _record(run_id, claims)
    if row["status"] != "waiting_approval":
        raise HTTPException(status_code=409, detail="Workflow is not waiting for approval")
    if claims["sub"] == row["requester"]:
        raise HTTPException(status_code=403, detail="Requester cannot approve their own workflow")
    pending = row["step_results"][-1]
    if pending["step_id"] != step_id or pending["status"] != "waiting_approval":
        raise HTTPException(status_code=404, detail="Pending approval step not found")
    pending.update(status="completed", approved_by=claims["sub"])
    row["steps_completed"] += 1
    # _continue_run changes state before its first await, rejecting duplicate decisions.
    await _continue_run(row)
    return _summary(row)
