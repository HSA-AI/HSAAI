
from __future__ import annotations
import time, uuid
from .schemas import WorkflowRunRequest, AgentRunRequest, ObservabilityEvent
from .agent_runtime import run_agent
from .observability import record_event

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
    for step in steps:
        if step["type"] == "agent":
            agent_id = step.get("input", {}).get("agent_id", "supervisor")
            agent_result = run_agent(AgentRunRequest(agent_id=agent_id, task=req.goal, context=req.context))
            trace.append({"id": step["id"], "type": "agent", "status": "completed", "agent_run_id": agent_result["run_id"]})
        elif step["type"] == "approval":
            trace.append({"id": step["id"], "type": "approval", "status": "waiting", "detail": "human approval required"})
        else:
            trace.append({"id": step["id"], "type": step["type"], "status": "completed"})
    elapsed = int((time.time()-started)*1000)
    record_event(ObservabilityEvent(event_type="workflow_run", component="workflow_engine", tenant_id=req.context.tenant_id, workspace_id=req.context.workspace_id, latency_ms=elapsed, success=True, risk_level="medium", metadata={"workflow_id": req.workflow_id, "workflow_run_id": workflow_run_id}))
    return {"workflow_run_id": workflow_run_id, "workflow_id": req.workflow_id, "goal": req.goal, "status": "completed_with_controls", "trace": trace, "elapsed_ms": elapsed}
