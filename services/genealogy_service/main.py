"""HSAAI Intelligence Genealogy Service — v0.4.0
Tracks the lineage of every piece of knowledge."""
import os, sys, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from common.genealogy import genealogy_engine
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
except ImportError:
    async def _auth_dep():
        from fastapi import HTTPException
        raise HTTPException(503, "Authentication module unavailable")

logger = logging.getLogger("genealogy_service")
app = FastAPI(title="HSAAI Intelligence Genealogy", version="0.4.0")

class NodeRegistration(BaseModel):
    node_id: str
    node_type: str
    content: str
    parent_ids: list[str] = []
    branch: str = "main"
    value: float = 0.0

@app.get("/health")
def health(): return {"status": "ok", "service": "genealogy", **genealogy_engine.stats()}

@app.post("/v1/register")
def register_node(req: NodeRegistration, claims: dict = Depends(_auth_dep)):
    node = genealogy_engine.register(req.node_id, req.node_type, req.content,
                                      req.parent_ids, req.branch, req.value)
    return node.__dict__

@app.get("/v1/trace/{node_id}")
def trace_lineage(node_id: str, claims: dict = Depends(_auth_dep)):
    return genealogy_engine.trace_lineage(node_id)

@app.get("/v1/influential")
def most_influential(limit: int = 10, claims: dict = Depends(_auth_dep)):
    return {"nodes": genealogy_engine.most_influential(limit)}

@app.get("/v1/roots")
def find_roots(branch: str = None, claims: dict = Depends(_auth_dep)):
    return {"roots": genealogy_engine.find_roots(branch)}

@app.get("/v1/stats")
def stats(claims: dict = Depends(_auth_dep)):
    return genealogy_engine.stats()
