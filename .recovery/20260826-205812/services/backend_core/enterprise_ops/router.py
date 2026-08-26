from __future__ import annotations

from fastapi import APIRouter, Depends
from backend_core.security.rbac import require_permission
from .service import enterprise_ops_service

router = APIRouter(prefix="/v1/enterprise-ops", tags=["HSAAI Enterprise Operations Centers"])

@router.get("/overview", dependencies=[Depends(require_permission("observability:read"))])
def overview():
    return enterprise_ops_service.full_overview()

@router.get("/agent-control-center", dependencies=[Depends(require_permission("agents:read"))])
def agent_control_center():
    return enterprise_ops_service.agent_control_center()

@router.get("/workflow-center", dependencies=[Depends(require_permission("workflows:read"))])
def workflow_center():
    return enterprise_ops_service.workflow_center()

@router.get("/integrations-monitoring", dependencies=[Depends(require_permission("connectors:read"))])
def integrations_monitoring():
    return enterprise_ops_service.integrations_monitoring()

@router.get("/executive-dashboard", dependencies=[Depends(require_permission("admin:read"))])
def executive_dashboard():
    return enterprise_ops_service.executive_dashboard()

@router.get("/ai-operations-analytics", dependencies=[Depends(require_permission("observability:read"))])
def ai_operations_analytics():
    return enterprise_ops_service.ai_operations_analytics()
