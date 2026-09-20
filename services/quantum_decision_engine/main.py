"""HSAAI Quantum Decision Engine Service — v0.5.0"""
import os, sys, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
from fastapi import FastAPI, Depends
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
except ImportError:
    async def _auth_dep():
        from fastapi import HTTPException
        raise HTTPException(503, "Authentication module unavailable")
from common.quantum_decision import *

logger = logging.getLogger("quantum_decision_engine")
app = FastAPI(title="HSAAI Quantum Decision Engine", version="0.5.0")

# Get the module-level engine instance
import common.quantum_decision as pkg_mod
engine_name = [k for k in dir(pkg_mod) if k.endswith('_engine') and not k.startswith('_')][0]
engine = getattr(pkg_mod, engine_name)

@app.get("/health")
def health():
    stats = engine.stats() if hasattr(engine, 'stats') else {}
    return {"status": "ok", "service": "quantum_decision_engine", **stats}

# Service-specific endpoints based on package
from pydantic import BaseModel
class QuantumRequest(BaseModel):
    question: str
    alternatives: list[str] = []
    context: dict = {}
    universes_per_alt: int = 100

@app.post("/v1/decide")
async def decide(req: QuantumRequest, claims: dict = Depends(_auth_dep)):
    decision = await quantum_engine.decide(req.question, req.alternatives,
                                            req.context, req.universes_per_alt)
    return decision.__dict__

@app.get("/v1/decisions")
def get_decisions(limit: int = 20, claims: dict = Depends(_auth_dep)):
    return {"decisions": quantum_engine.get_decisions(limit)}
