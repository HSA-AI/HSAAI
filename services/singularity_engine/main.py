"""HSAAI Intelligence Singularity Service — v0.6.0"""
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
from common.singularity import singularity_engine
engine = singularity_engine
logger = logging.getLogger("singularity_engine")
app = FastAPI(title="HSAAI Intelligence Singularity", version="0.6.0")

@app.get("/health")
def health():
    stats = engine.stats() if hasattr(engine, 'stats') else {}
    return {"status": "ok", "service": "singularity_engine", **stats}
class FeedInput(BaseModel):
    layer_name: str
    insight: str
    confidence: float = 0.5

class ConvergenceCheck(BaseModel):
    question: str = ""

@app.post("/v1/feed")
def feed(req: FeedInput, claims: dict = Depends(_auth_dep)):
    singularity_engine.feed_insight(req.layer_name, req.insight, req.confidence)
    return {"fed": True}

@app.post("/v1/check")
async def check(req: ConvergenceCheck, claims: dict = Depends(_auth_dep)):
    result = await singularity_engine.check_for_convergence(req.question)
    return result.__dict__ if result else {"convergence": False, "message": "No convergence detected."}

@app.get("/v1/singularities")
def get_singularities(min_transcendence: float = 0.0, limit: int = 10, claims: dict = Depends(_auth_dep)):
    return {"singularities": singularity_engine.get_singularities(min_transcendence, limit)}
