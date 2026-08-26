from fastapi import FastAPI, Depends  # FIX v2.1 (P0): add Depends import
# SECURITY FIX v2.0: Add shared service auth
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..', '..', 'packages'))
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
    _AUTH_AVAILABLE = True
except ImportError as _e:
    _AUTH_AVAILABLE = False
    _AUTH_LOAD_ERROR = str(_e)
    async def _auth_dep():  # type: ignore
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Authentication module unavailable. Service cannot accept requests.")

from pydantic import BaseModel
from multi_agents.agents import SupervisorAgent, AGENTS, MEMORY

app = FastAPI(title="HSAAI Multi Agents Runtime", version="4.0.0")
supervisor = SupervisorAgent()

class RunRequest(BaseModel):
    message: str
    context: str = ""
    tenant_id: str = "default"
    workspace_id: str = "default"

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "multi_agents",
        "agents": list(AGENTS.keys()),
        "runtime": "supervisor+tools+memory-ready",
    }

@app.post("/v1/run")
async def run(req: RunRequest, claims: dict = Depends(_auth_dep)):  # FIX v2.1: async
    decision = supervisor.route(req.message)
    recent = MEMORY.recent(req.tenant_id, req.workspace_id)
    # FIX B-03: agent.run is now async — must await it.
    result = await AGENTS[decision.agent].run(req.message, req.context, memory=recent, tenant_id=req.tenant_id, workspace_id=req.workspace_id)
    MEMORY.remember(req.tenant_id, req.workspace_id, result["agent"], req.message)
    return {"route": decision.__dict__, "result": result, "tenant_id": req.tenant_id, "workspace_id": req.workspace_id}
