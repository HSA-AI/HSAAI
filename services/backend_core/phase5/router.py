
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from backend_core.security.rbac import get_current_claims, require_permission
from common.security.request_policy import verified_scope, authorization_context
from .schemas import AgentRunRequest, WorkflowRunRequest, ModelRouteRequest, EnterpriseSearchRequest, ObservabilityEvent
from .agent_runtime import list_agents, run_agent
from .workflow_engine import run_workflow
from .model_router import route_model
from .enterprise_search import unified_search
from .observability import record_event, ai_metrics, read_events

async def _scoped_claims(request: Request, claims: dict = Depends(get_current_claims)):
    try:
        verified_scope(claims)
    except ValueError as exc:
        raise HTTPException(403, str(exc)) from exc
    token = authorization_context.set(request.headers.get("authorization", ""))
    try:
        yield claims
    finally:
        authorization_context.reset(token)


def _context(payload, claims):
    payload.context.tenant_id, payload.context.workspace_id = verified_scope(claims)
    payload.context.user_id = claims["sub"]
    return payload


router = APIRouter(prefix="/v1/ops", tags=["enterprise-ai-operations"])

@router.get("/agents")
def agents(claims: dict = Depends(_scoped_claims), permission: dict = Depends(require_permission("agents:read"))):
    return list_agents()

@router.post("/agents/run")
def agents_run(payload: AgentRunRequest, claims: dict = Depends(_scoped_claims), permission: dict = Depends(require_permission("agents:execute"))):
    return run_agent(_context(payload, claims))

@router.post("/workflows/run")
def workflows_run(payload: WorkflowRunRequest, claims: dict = Depends(_scoped_claims), permission: dict = Depends(require_permission("workflows:execute"))):
    return run_workflow(_context(payload, claims))

@router.post("/models/route")
def models_route(payload: ModelRouteRequest, claims: dict = Depends(_scoped_claims), permission: dict = Depends(require_permission("agents:read"))):
    return route_model(payload)

@router.post("/search")
def enterprise_search(payload: EnterpriseSearchRequest, claims: dict = Depends(_scoped_claims), permission: dict = Depends(require_permission("knowledge:read"))):
    return unified_search(_context(payload, claims))

@router.get("/observability/metrics")
def observability_metrics(claims: dict = Depends(_scoped_claims), permission: dict = Depends(require_permission("observability:read"))):
    tenant, workspace = verified_scope(claims)
    return ai_metrics(tenant_id=tenant, workspace_id=workspace)

@router.get("/observability/events")
def observability_events(limit: int = 100, claims: dict = Depends(_scoped_claims), permission: dict = Depends(require_permission("observability:read"))):
    tenant, workspace = verified_scope(claims)
    return {"events": read_events(limit, tenant_id=tenant, workspace_id=workspace)}

@router.post("/observability/events")
def observability_record(payload: ObservabilityEvent, claims: dict = Depends(_scoped_claims), permission: dict = Depends(require_permission("agents:execute"))):
    payload.tenant_id, payload.workspace_id = verified_scope(claims)
    return record_event(payload)
