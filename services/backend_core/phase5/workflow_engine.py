
from __future__ import annotations
import time, uuid
from .schemas import WorkflowRunRequest, AgentRunRequest, ObservabilityEvent
from .agent_runtime import run_agent
from .observability import record_event
from .enterprise_search import unified_search
from .schemas import EnterpriseSearchRequest
from common.security.request_policy import verified_scope

DEFAULT_STEPS = [
    {"id": "policy", "type": "policy_check", "name": "Tenant/RBAC policy check", "input": {}},
    {"id": "knowledge", "type": "rag", "name": "Retrieve enterprise context", "input": {}},
    {"id": "supervisor", "type": "agent", "name": "Supervisor synthesis", "input": {"agent_id": "supervisor"}},
]

def run_workflow(req: WorkflowRunRequest) -> dict:
    started = time.time()
    workflow_run_id = f"wf_{uuid.uuid4().hex[:12]}"
    steps = [s.model_dump() for s in req.steps] if req.steps else DEFAULT_STEPS
    trace=[]
    status = "completed_with_controls"
    for step in steps:
        kind = step["type"]
        item = {"id": step["id"], "type": kind}
        if kind in {"agent", "llm"}:
            result = run_agent(AgentRunRequest(agent_id=step.get("input", {}).get("agent_id", "supervisor"), task=req.goal, context=req.context))
            item.update(status=result["status"], agent_run_id=result["run_id"])
        elif kind == "rag":
            result = unified_search(EnterpriseSearchRequest(query=req.goal, context=req.context, sources=["rag"]))
            item.update(status=result["status"], results_count=result["count"])
        elif kind == "approval":
            item.update(status="waiting_approval", detail="Human approval required")
        elif kind == "policy_check":
            try:
                verified_scope(req.context.model_dump())
                item.update(status="completed", detail="Scope validated; endpoint RBAC enforced by router")
            except ValueError:
                item.update(status="failed", detail="Explicit scope required")
        else:
            item.update(status="failed", detail="Integration executor not configured")
        trace.append(item)
        if item["status"] != "completed":
            status = item["status"]
            break
    elapsed = int((time.time()-started)*1000)
    record_event(ObservabilityEvent(event_type="workflow_run", component="workflow_engine", tenant_id=req.context.tenant_id, workspace_id=req.context.workspace_id, latency_ms=elapsed, success=status == "completed_with_controls", risk_level="medium", metadata={"workflow_id": req.workflow_id, "workflow_run_id": workflow_run_id}))
    return {"workflow_run_id": workflow_run_id, "workflow_id": req.workflow_id, "goal": req.goal, "status": status, "trace": trace, "elapsed_ms": elapsed}
