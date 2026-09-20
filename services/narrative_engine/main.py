"""HSAAI Cognitive Narrative Service — v0.5.0"""
import os, sys, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
from fastapi import FastAPI, Depends
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
except ImportError:
    async def _auth_dep():
        from fastapi import HTTPException
        raise HTTPException(503, "Authentication module unavailable")
from common.narrative import *

logger = logging.getLogger("narrative_engine")
app = FastAPI(title="HSAAI Cognitive Narrative", version="0.5.0")

# Get the module-level engine instance
import common.narrative as pkg_mod
engine_name = [k for k in dir(pkg_mod) if k.endswith('_engine') and not k.startswith('_')][0]
engine = getattr(pkg_mod, engine_name)

@app.get("/health")
def health():
    stats = engine.stats() if hasattr(engine, 'stats') else {}
    return {"status": "ok", "service": "narrative_engine", **stats}

# Service-specific endpoints based on package
from pydantic import BaseModel
class NarrativeRequest(BaseModel):
    events: list[dict] = []
    context: dict = {}

@app.post("/v1/construct")
async def construct(req: NarrativeRequest, claims: dict = Depends(_auth_dep)):
    narrative = await narrative_engine.construct_narrative(req.events, req.context)
    return narrative.__dict__

@app.get("/v1/narratives")
def get_narratives(limit: int = 20, claims: dict = Depends(_auth_dep)):
    return {"narratives": narrative_engine.get_narratives(limit)}
