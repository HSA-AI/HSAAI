"""HSAAI Cognitive Immune System Service — v0.6.0"""
import os, sys, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
from fastapi import FastAPI, Depends
from pydantic import BaseModel
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
except ImportError:
    async def _auth_dep():
        from fastapi import HTTPException
        raise HTTPException(503, "Authentication module unavailable")
from common.immune_system import immune_system
engine = immune_system
logger = logging.getLogger("immune_system")
app = FastAPI(title="HSAAI Cognitive Immune System", version="0.6.0")

@app.get("/health")
def health():
    stats = engine.stats() if hasattr(engine, 'stats') else {}
    return {"status": "ok", "service": "immune_system", **stats}
class ScanInput(BaseModel):
    content: str
    source: str = "unknown"

@app.post("/v1/scan")
async def scan_content(req: ScanInput, claims: dict = Depends(_auth_dep)):
    pathogen = await immune_system.scan(req.content, req.source)
    return pathogen.__dict__ if pathogen else {"clean": True, "message": "No pathogens detected."}

@app.get("/v1/pathogens")
def get_pathogens(blocked_only: bool = False, limit: int = 20, claims: dict = Depends(_auth_dep)):
    return {"pathogens": immune_system.get_pathogens(blocked_only, limit)}

@app.get("/v1/antibodies")
def get_antibodies(claims: dict = Depends(_auth_dep)):
    return {"antibodies": immune_system.get_antibodies()}
