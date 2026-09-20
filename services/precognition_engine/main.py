"""HSAAI Precognition Engine Service — v0.6.0"""
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
from common.precognition import precognition_engine
engine = precognition_engine
logger = logging.getLogger("precognition_engine")
app = FastAPI(title="HSAAI Precognition Engine", version="0.6.0")

@app.get("/health")
def health():
    stats = engine.stats() if hasattr(engine, 'stats') else {}
    return {"status": "ok", "service": "precognition_engine", **stats}
class SignalInput(BaseModel):
    signal_type: str
    description: str
    strength: float = 0.5
    source: str = "monitor"

@app.post("/v1/signal")
async def ingest_signal(req: SignalInput, claims: dict = Depends(_auth_dep)):
    signal = await precognition_engine.ingest_signal(req.signal_type, req.description, req.strength, req.source)
    return signal.__dict__

@app.post("/v1/scan")
async def scan(claims: dict = Depends(_auth_dep)):
    precogs = await precognition_engine.scan_all_signals()
    return {"precognitions": [p.__dict__ for p in precogs]}

@app.get("/v1/precognitions")
def get_precognitions(status: str = None, limit: int = 20, claims: dict = Depends(_auth_dep)):
    return {"precognitions": precognition_engine.get_precognitions(status, limit)}

class VerificationInput(BaseModel):
    precognition_id: str
    event_occurred: bool
    timing_accurate: bool = False
    impact_accurate: bool = False

@app.post("/v1/verify")
async def verify(req: VerificationInput, claims: dict = Depends(_auth_dep)):
    await precognition_engine.verify(req.precognition_id, req.event_occurred, req.timing_accurate, req.impact_accurate)
    return {"verified": True}
