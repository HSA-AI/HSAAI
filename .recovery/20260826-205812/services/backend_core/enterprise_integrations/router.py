from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from backend_core.db.database import SessionLocal
from backend_core.security.rbac import require_permission, get_current_claims
from .schemas import IntegrationConfigureIn, ConnectorFetchIn
from .services import integration_service

router = APIRouter(prefix="/v1/enterprise-integrations", tags=["Enterprise Integrations"])

def _scope(claims: dict):
    return claims.get("tenant_id", "default"), claims.get("workspace_id", "default")

@router.get("/overview", dependencies=[Depends(require_permission("connectors:read"))])
def overview(claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = _scope(claims)
    try: return integration_service.overview(db, tenant, workspace)
    finally: db.close()

@router.get("/supported", dependencies=[Depends(require_permission("connectors:read"))])
def supported():
    from .connector_registry import registry
    return {"supported": registry.supported()}

@router.get("/connectors", dependencies=[Depends(require_permission("connectors:read"))])
def list_connectors(claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = _scope(claims)
    try: return {"connectors": integration_service.list_connectors(db, tenant, workspace)}
    finally: db.close()

@router.put("/connectors", dependencies=[Depends(require_permission("connectors:admin"))])
def configure_connector(payload: IntegrationConfigureIn, claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = _scope(claims)
    try: return integration_service.configure(db, payload.dict(), claims, tenant, workspace)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc))
    finally: db.close()

@router.post("/connectors/{key}/test", dependencies=[Depends(require_permission("connectors:admin"))])
def test_connector(key: str, claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = _scope(claims)
    try: return integration_service.test_connection(db, key, claims, tenant, workspace)
    except ValueError as exc: raise HTTPException(status_code=404, detail=str(exc))
    finally: db.close()

@router.post("/connectors/{key}/fetch", dependencies=[Depends(require_permission("connectors:read"))])
def fetch_connector_data(key: str, payload: ConnectorFetchIn, claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = _scope(claims)
    try: return integration_service.fetch(db, key, payload.query, claims, tenant, workspace)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc))
    finally: db.close()

@router.post("/connectors/{key}/sync", dependencies=[Depends(require_permission("connectors:sync"))])
def sync_connector(key: str, claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = _scope(claims)
    try: return integration_service.sync(db, key, claims, tenant, workspace)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc))
    finally: db.close()

@router.get("/agents/{agent_key}/data-sources", dependencies=[Depends(require_permission("agents:read"))])
def agent_data_sources(agent_key: str):
    return integration_service.agent_sources(agent_key)

@router.get("/workflows/{template_key}/connectors", dependencies=[Depends(require_permission("workflows:read"))])
def workflow_connectors(template_key: str):
    return integration_service.workflow_sources(template_key)

@router.get("/audit-logs", dependencies=[Depends(require_permission("audit:read"))])
def audit_logs(claims: dict = Depends(get_current_claims)):
    db = SessionLocal(); tenant, workspace = _scope(claims)
    try: return {"logs": integration_service.audit_logs(db, tenant, workspace)}
    finally: db.close()
