
from fastapi import APIRouter, Depends
from backend_core.security.rbac import require_permission
from .service import service

router = APIRouter(prefix='/v1/ai-operations', tags=['AI Operations Center'])

@router.get('/overview', dependencies=[Depends(require_permission('ai_operations:read'))])
def overview(): return service.overview()

@router.get('/providers', dependencies=[Depends(require_permission('ai_operations:read'))])
def providers(): return {'providers': service.providers()}

@router.get('/deployments', dependencies=[Depends(require_permission('ai_operations:read'))])
def deployments(): return {'deployments': service.deployments()}

@router.get('/gpu', dependencies=[Depends(require_permission('ai_operations:read'))])
def gpu(): return {'gpu_nodes': service.gpu()}

@router.get('/incidents', dependencies=[Depends(require_permission('ai_operations:read'))])
def incidents(): return {'incidents': service.incidents()}
