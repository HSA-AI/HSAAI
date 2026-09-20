
from __future__ import annotations
from fastapi import APIRouter, Depends, Header, HTTPException
from backend_core.db.database import SessionLocal
from backend_core.security.rbac import require_permission, get_current_claims
from .schemas import AgentRouteRequest, WorkflowStartRequest, ConnectorConfigIn, ApprovalRequestIn, ApprovalDecisionIn
from .services import supervisor_service, workflow_service, connector_service, observability_service, approval_service

router = APIRouter(prefix="/v1/enterprise-upgrade", tags=["Enterprise Upgrade"])

def scope(claims: dict):
    return claims.get("tenant_id", "default"), claims.get("workspace_id", "default")

@router.get("/agents/registry", dependencies=[Depends(require_permission("agents:read"))])
def agent_registry(claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = scope(claims)
    try: return {"agents": supervisor_service.registry(db, tenant, workspace)}
    finally: db.close()

@router.post("/agents/supervisor/route", dependencies=[Depends(require_permission("agents:execute"))])
def supervisor_route(payload: AgentRouteRequest, claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = claims.get("tenant_id","default"), payload.workspace_id or claims.get("workspace_id","default")
    try: return supervisor_service.route(db, message=payload.message, claims=claims, tenant_id=tenant, workspace_id=workspace, session_id=payload.session_id)
    finally: db.close()

@router.get("/agents/health", dependencies=[Depends(require_permission("agents:read"))])
def agent_health(claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = scope(claims)
    try: return supervisor_service.health(db, tenant, workspace)
    finally: db.close()

@router.get("/workflows/templates", dependencies=[Depends(require_permission("workflows:read"))])
def workflow_templates(claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = scope(claims)
    try: return {"templates": workflow_service.templates(db, tenant, workspace)}
    finally: db.close()

@router.post("/workflows/start", dependencies=[Depends(require_permission("workflows:execute"))])
def workflow_start(payload: WorkflowStartRequest, claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = scope(claims)
    try: return workflow_service.start(db, template_key=payload.template_key, payload=payload.payload, requested_by=payload.requested_by or claims.get("sub","system"), tenant_id=tenant, workspace_id=workspace)
    except ValueError as exc: raise HTTPException(status_code=404, detail=str(exc))
    finally: db.close()

@router.get("/workflows/executions", dependencies=[Depends(require_permission("workflows:read"))])
def workflow_executions(claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = scope(claims)
    try: return {"executions": workflow_service.executions(db, tenant, workspace)}
    finally: db.close()

@router.get("/connectors", dependencies=[Depends(require_permission("connectors:read"))])
def connectors(claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = scope(claims)
    try: return {"supported": connector_service.SUPPORTED, "connectors": connector_service.list(db, tenant, workspace)}
    finally: db.close()

@router.post("/connectors", dependencies=[Depends(require_permission("connectors:admin"))])
def connector_create(payload: ConnectorConfigIn, claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = scope(claims)
    try: return connector_service.create(db, payload.dict(), tenant, workspace)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc))
    finally: db.close()

@router.post("/connectors/{key}/test", dependencies=[Depends(require_permission("connectors:admin"))])
def connector_test(key: str, claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = scope(claims)
    try: return connector_service.test(db, key, tenant, workspace)
    except ValueError as exc: raise HTTPException(status_code=404, detail=str(exc))
    finally: db.close()

@router.get("/observability/dashboard", dependencies=[Depends(require_permission("observability:read"))])
def observability_dashboard(claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = scope(claims)
    try: return observability_service.dashboard(db, tenant, workspace)
    finally: db.close()

@router.post("/approvals", dependencies=[Depends(require_permission("approvals:create"))])
def approval_create(payload: ApprovalRequestIn, claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = scope(claims)
    try: return approval_service.create(db, data=payload.dict(), claims=claims, tenant_id=tenant, workspace_id=workspace)
    finally: db.close()

@router.get("/approvals/queue", dependencies=[Depends(require_permission("approvals:read"))])
def approval_queue(claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = scope(claims)
    try: return {"approvals": approval_service.queue(db, tenant, workspace)}
    finally: db.close()

@router.post("/approvals/{approval_id}/approve", dependencies=[Depends(require_permission("approvals:decide"))])
def approval_approve(approval_id: str, payload: ApprovalDecisionIn, claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = scope(claims)
    try: return approval_service.decide(db, approval_id, "approved", payload.comment, claims, tenant, workspace)
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc: raise HTTPException(status_code=404, detail=str(exc))
    finally: db.close()

@router.post("/approvals/{approval_id}/reject", dependencies=[Depends(require_permission("approvals:decide"))])
def approval_reject(approval_id: str, payload: ApprovalDecisionIn, claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = scope(claims)
    try: return approval_service.decide(db, approval_id, "rejected", payload.comment, claims, tenant, workspace)
    except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc: raise HTTPException(status_code=404, detail=str(exc))
    finally: db.close()
