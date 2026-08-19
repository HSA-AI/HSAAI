
from __future__ import annotations
from fastapi import APIRouter
from .schemas import AgentRunRequest, WorkflowRunRequest, ModelRouteRequest, EnterpriseSearchRequest, ObservabilityEvent
from .agent_runtime import list_agents, run_agent
from .workflow_engine import run_workflow
from .model_router import route_model
from .enterprise_search import unified_search
from .observability import record_event, ai_metrics, read_events

router = APIRouter(prefix="/v1/ops", tags=["enterprise-ai-operations"])

@router.get("/agents")
def agents():
    return list_agents()

@router.post("/agents/run")
def agents_run(payload: AgentRunRequest):
    return run_agent(payload)

@router.post("/workflows/run")
def workflows_run(payload: WorkflowRunRequest):
    return run_workflow(payload)

@router.post("/models/route")
def models_route(payload: ModelRouteRequest):
    return route_model(payload)

@router.post("/search")
def enterprise_search(payload: EnterpriseSearchRequest):
    return unified_search(payload)

@router.get("/observability/metrics")
def observability_metrics():
    return ai_metrics()

@router.get("/observability/events")
def observability_events(limit: int = 100):
    return {"events": read_events(limit)}

@router.post("/observability/events")
def observability_record(payload: ObservabilityEvent):
    return record_event(payload)
