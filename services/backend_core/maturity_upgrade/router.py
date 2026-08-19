from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from backend_core.db.database import SessionLocal
from backend_core.security.rbac import require_permission, get_current_claims
from .schemas import AgentRouteRequest, WorkflowStartRequest, WorkflowActionRequest, ConnectorRuntimeRequest, ObservabilityEventIn
from .agent_orchestration import agent_orchestrator
from .workflow_runtime import workflow_engine
from .connectors_runtime import connector_runtime
from .observability import observability_service

router = APIRouter(prefix="/v1/maturity", tags=["HSAAI Advanced Maturity Upgrade"])

def _scope(claims: dict):
    return claims.get("tenant_id", "default"), claims.get("workspace_id", "default")

@router.get("/overview", dependencies=[Depends(require_permission("admin:read"))])
def overview(claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = _scope(claims)
    try:
        return {
            "maturity_level": "advanced_enterprise_ai_platform",
            "upgrades": {
                "agent_orchestration": "advanced",
                "workflow_automation": "advanced",
                "enterprise_connectors": "advanced_runtime_ready",
                "observability": "mature_operational_dashboards",
            },
            "agents": agent_orchestrator.registry(),
            "workflows": workflow_engine.templates(),
            "connectors": connector_runtime.health_matrix(db, tenant, workspace),
            "observability": observability_service.dashboard(db, tenant, workspace),
        }
    finally:
        db.close()

@router.get("/agents/registry", dependencies=[Depends(require_permission("agents:read"))])
def agents_registry():
    return agent_orchestrator.registry()

@router.post("/agents/route", dependencies=[Depends(require_permission("agents:read"))])
def route_agent(payload: AgentRouteRequest, claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = _scope(claims)
    try:
        payload.tenant_id = tenant; payload.workspace_id = workspace
        payload.roles = payload.roles or claims.get("roles", [])
        payload.user_id = payload.user_id or claims.get("sub", "system")
        return agent_orchestrator.route(db, payload)
    finally:
        db.close()

@router.get("/agents/performance", dependencies=[Depends(require_permission("agents:read"))])
def agent_performance(claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = _scope(claims)
    try: return agent_orchestrator.performance(db, tenant, workspace)
    finally: db.close()

@router.get("/workflows/templates", dependencies=[Depends(require_permission("workflows:read"))])
def workflow_templates():
    return workflow_engine.templates()

@router.post("/workflows/start", dependencies=[Depends(require_permission("workflows:write"))])
def start_workflow(payload: WorkflowStartRequest, claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = _scope(claims)
    try:
        payload.tenant_id = tenant; payload.workspace_id = workspace
        if payload.requested_by == "system": payload.requested_by = claims.get("sub", "system")
        return workflow_engine.start(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        db.close()

@router.post("/workflows/action", dependencies=[Depends(require_permission("workflows:approve"))])
def workflow_action(payload: WorkflowActionRequest, claims: dict = Depends(get_current_claims)):
    db = SessionLocal()
    try:
        if payload.actor == "system": payload.actor = claims.get("sub", "system")
        return workflow_engine.action(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    finally:
        db.close()

@router.get("/workflows/executions", dependencies=[Depends(require_permission("workflows:read"))])
def workflow_executions(claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = _scope(claims)
    try: return workflow_engine.list(db, tenant, workspace)
    finally: db.close()

@router.get("/connectors/health", dependencies=[Depends(require_permission("connectors:read"))])
def connectors_health(claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = _scope(claims)
    try: return connector_runtime.health_matrix(db, tenant, workspace)
    finally: db.close()

@router.post("/connectors/probe", dependencies=[Depends(require_permission("connectors:admin"))])
def connectors_probe(payload: ConnectorRuntimeRequest, claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = _scope(claims)
    try: return connector_runtime.run_probe(db, payload.connector_key, claims, tenant, workspace)
    finally: db.close()

@router.post("/observability/events", dependencies=[Depends(require_permission("observability:write"))])
def record_observability(event: ObservabilityEventIn):
    db = SessionLocal()
    try: return observability_service.record(db, event)
    finally: db.close()

@router.get("/observability/dashboard", dependencies=[Depends(require_permission("observability:read"))])
def observability_dashboard(claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = _scope(claims)
    try: return observability_service.dashboard(db, tenant, workspace)
    finally: db.close()
