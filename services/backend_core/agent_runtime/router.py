
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from backend_core.security.rbac import require_permission
from .service import service

class AgentRunRequest(BaseModel):
    agent_id: str
    prompt: str
    session_id: str = 'default'

class CollaborationRequest(BaseModel):
    agents: list[str]
    task: str

router = APIRouter(prefix='/v1/agent-runtime', tags=['Agent Runtime Engine'])

@router.post('/run', dependencies=[Depends(require_permission('agents:execute'))])
def run_agent(payload: AgentRunRequest): return service.run(payload.agent_id, payload.prompt, payload.session_id)

@router.post('/collaborate', dependencies=[Depends(require_permission('agents:execute'))])
def collaborate(payload: CollaborationRequest): return service.collaborate(payload.agents, payload.task)

@router.get('/metrics', dependencies=[Depends(require_permission('agents:read'))])
def metrics(): return service.metrics()
