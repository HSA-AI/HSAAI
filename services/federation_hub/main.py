"""HSAAI Federation Hub — v0.3.0
Cross-organization intelligence sharing mesh."""
import os, sys, logging, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from common.federation import federation_mesh, FederationNode, TrustTier
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
except ImportError:
    async def _auth_dep():
        from fastapi import HTTPException
        raise HTTPException(503, "Authentication module unavailable")

logger = logging.getLogger("federation_hub")
app = FastAPI(title="HSAAI Federation Hub", version="0.3.0")

class NodeRegistration(BaseModel):
    node_id: str
    name: str
    org_type: str = "department"
    trust_tier: str = "partner"
    endpoint: str = ""
    shared_intelligence: list[str] = []
    consumed_intelligence: list[str] = []

class IntelligenceQuery(BaseModel):
    from_node: str
    to_node: str
    query_type: str = "intelligence_query"
    payload: dict = {}

@app.get("/health")
def health(): return {"status": "ok", "service": "federation_hub", **federation_mesh.stats()}

@app.post("/v1/register")
def register(node: NodeRegistration, claims: dict = Depends(_auth_dep)):
    fn = FederationNode(
        node_id=node.node_id, name=node.name, org_type=node.org_type,
        trust_tier=TrustTier(node.trust_tier), endpoint=node.endpoint,
        shared_intelligence=node.shared_intelligence,
        consumed_intelligence=node.consumed_intelligence,
    )
    federation_mesh.register_node(fn)
    return {"status": "registered", "node_id": node.node_id}

@app.get("/v1/nodes")
def list_nodes(claims: dict = Depends(_auth_dep)):
    return {"nodes": federation_mesh.list_nodes()}

@app.post("/v1/query")
async def query_intelligence(q: IntelligenceQuery, claims: dict = Depends(_auth_dep)):
    resp = await federation_mesh.query_intelligence(q.from_node, q.to_node, q.query_type, q.payload)
    return resp.__dict__

@app.get("/v1/stats")
def stats(claims: dict = Depends(_auth_dep)):
    return federation_mesh.stats()
