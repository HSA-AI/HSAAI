"""HSAAI Collective Intelligence Service — v0.6.0"""
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
from common.collective_intelligence import collective_intelligence_engine
engine = collective_intelligence_engine
logger = logging.getLogger("collective_intelligence_engine")
app = FastAPI(title="HSAAI Collective Intelligence", version="0.6.0")

@app.get("/health")
def health():
    stats = engine.stats() if hasattr(engine, 'stats') else {}
    return {"status": "ok", "service": "collective_intelligence_engine", **stats}
class ContributionInput(BaseModel):
    source_type: str = "human"
    source_id: str = ""
    content: str = ""
    intelligence_type: str = "analytical"
    confidence: float = 0.5

class SynthesisInput(BaseModel):
    human_content: str = ""
    ai_content: str = ""
    context: str = ""

@app.post("/v1/contribute")
async def contribute(req: ContributionInput, claims: dict = Depends(_auth_dep)):
    c = await collective_intelligence_engine.contribute(req.source_type, req.source_id, req.content, req.intelligence_type, req.confidence)
    return c.__dict__

@app.post("/v1/synthesize")
async def synthesize(req: SynthesisInput, claims: dict = Depends(_auth_dep)):
    insight = await collective_intelligence_engine.synthesize(req.human_content, req.ai_content, req.context)
    return insight.__dict__

@app.get("/v1/insights")
def get_insights(limit: int = 20, claims: dict = Depends(_auth_dep)):
    return {"insights": collective_intelligence_engine.get_insights(limit)}
