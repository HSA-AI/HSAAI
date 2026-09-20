"""HSAAI Self-Reflection Engine Service — v0.5.0"""
import os, sys, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
from fastapi import FastAPI, Depends
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
except ImportError:
    async def _auth_dep():
        from fastapi import HTTPException
        raise HTTPException(503, "Authentication module unavailable")
from common.reflection import *

logger = logging.getLogger("reflection_engine")
app = FastAPI(title="HSAAI Self-Reflection Engine", version="0.5.0")

# Get the module-level engine instance
import common.reflection as pkg_mod
engine_name = [k for k in dir(pkg_mod) if k.endswith('_engine') and not k.startswith('_')][0]
engine = getattr(pkg_mod, engine_name)

@app.get("/health")
def health():
    stats = engine.stats() if hasattr(engine, 'stats') else {}
    return {"status": "ok", "service": "reflection_engine", **stats}

# Service-specific endpoints based on package
from pydantic import BaseModel
class DecisionRecord(BaseModel):
    question: str = ""
    recommendation: str = ""
    confidence: float = 0.5
    outcome: str = ""
    agreed_with_user: bool = False

@app.post("/v1/record")
def record_decision(rec: DecisionRecord, claims: dict = Depends(_auth_dep)):
    reflection_engine.record_decision(rec.__dict__)
    return {"recorded": True}

@app.post("/v1/reflect")
async def reflect(trigger: str = "api", claims: dict = Depends(_auth_dep)):
    r = await reflection_engine.reflect(trigger)
    return r.__dict__

@app.get("/v1/reflections")
def get_reflections(limit: int = 20, claims: dict = Depends(_auth_dep)):
    return {"reflections": reflection_engine.get_reflections(limit)}

@app.get("/v1/biases")
def get_biases(claims: dict = Depends(_auth_dep)):
    return {"biases": reflection_engine.get_biases()}
