"""HSAAI Enterprise Intuition Service — v0.5.0"""
import os, sys, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
from fastapi import FastAPI, Depends
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
except ImportError:
    async def _auth_dep():
        from fastapi import HTTPException
        raise HTTPException(503, "Authentication module unavailable")
from common.intuition import *

logger = logging.getLogger("intuition_engine")
app = FastAPI(title="HSAAI Enterprise Intuition", version="0.5.0")

# Get the module-level engine instance
import common.intuition as pkg_mod
engine_name = [k for k in dir(pkg_mod) if k.endswith('_engine') and not k.startswith('_')][0]
engine = getattr(pkg_mod, engine_name)

@app.get("/health")
def health():
    stats = engine.stats() if hasattr(engine, 'stats') else {}
    return {"status": "ok", "service": "intuition_engine", **stats}

# Service-specific endpoints based on package
from pydantic import BaseModel
class IntuitionSense(BaseModel):
    context: dict = {}
class IntuitionTrain(BaseModel):
    experience_type: str = ""
    context: str = ""
    outcome: str = ""
    intuition_was_correct: bool = False
    lesson: str = ""

@app.post("/v1/sense")
async def sense(req: IntuitionSense, claims: dict = Depends(_auth_dep)):
    signal = await intuition_engine.sense(req.context)
    return signal.__dict__

@app.post("/v1/train")
def train(req: IntuitionTrain, claims: dict = Depends(_auth_dep)):
    intuition_engine.train(req.experience_type, req.context, req.outcome,
                           req.intuition_was_correct, req.lesson)
    return {"trained": True, "strength": intuition_engine.intuition_strength()}

@app.get("/v1/signals")
def get_signals(min_strength: float = 0.0, limit: int = 20, claims: dict = Depends(_auth_dep)):
    return {"signals": intuition_engine.get_signals(min_strength, limit)}
