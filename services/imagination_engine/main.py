"""HSAAI Strategic Imagination Service — v0.5.0"""
import os, sys, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
from fastapi import FastAPI, Depends
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
except ImportError:
    async def _auth_dep():
        from fastapi import HTTPException
        raise HTTPException(503, "Authentication module unavailable")
from common.imagination import *

logger = logging.getLogger("imagination_engine")
app = FastAPI(title="HSAAI Strategic Imagination", version="0.5.0")

# Get the module-level engine instance
import common.imagination as pkg_mod
engine_name = [k for k in dir(pkg_mod) if k.endswith('_engine') and not k.startswith('_')][0]
engine = getattr(pkg_mod, engine_name)

@app.get("/health")
def health():
    stats = engine.stats() if hasattr(engine, 'stats') else {}
    return {"status": "ok", "service": "imagination_engine", **stats}

# Service-specific endpoints based on package
from pydantic import BaseModel
class ImagineRequest(BaseModel):
    context: dict = {}
    count: int = 5
class InsightRequest(BaseModel):
    concepts: list[str] = []

@app.post("/v1/imagine")
async def imagine(req: ImagineRequest, claims: dict = Depends(_auth_dep)):
    futures = await imagination_engine.imagine_futures(req.context, req.count)
    return {"futures": [f.__dict__ for f in futures]}

@app.post("/v1/insight")
async def generate_insight(req: InsightRequest, claims: dict = Depends(_auth_dep)):
    insight = await imagination_engine.generate_creative_insight(req.concepts)
    return insight.__dict__

@app.get("/v1/futures")
def get_futures(category: str = None, limit: int = 20, claims: dict = Depends(_auth_dep)):
    return {"futures": imagination_engine.get_futures(category, limit)}
