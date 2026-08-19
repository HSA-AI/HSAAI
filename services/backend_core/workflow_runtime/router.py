
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from backend_core.security.rbac import require_permission
from .service import service

class StartWorkflowRequest(BaseModel):
    workflow_id: str
    payload: dict = {}

router = APIRouter(prefix='/v1/workflow-runtime', tags=['Workflow Runtime Engine'])

@router.post('/start', dependencies=[Depends(require_permission('workflows:execute'))])
def start(payload: StartWorkflowRequest): return service.start(payload.workflow_id, payload.payload)

@router.get('/history', dependencies=[Depends(require_permission('workflows:read'))])
def history(): return {'executions': service.history()}

@router.get('/schedules', dependencies=[Depends(require_permission('workflows:read'))])
def schedules(): return {'schedules': service.schedules()}

@router.get('/approvals', dependencies=[Depends(require_permission('workflows:approve'))])
def approvals(): return {'approvals': service.approvals.pending()}

@router.get('/metrics', dependencies=[Depends(require_permission('workflows:read'))])
def metrics(): return service.metrics()
