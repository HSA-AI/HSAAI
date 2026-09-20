"""HSAAI Causal Time Travel Service — v0.4.0
Rewind the enterprise and replay with alternative decisions."""
import os, sys, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from common.time_travel import time_travel_engine, HistoricalState
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
except ImportError:
    async def _auth_dep():
        from fastapi import HTTPException
        raise HTTPException(503, "Authentication module unavailable")

logger = logging.getLogger("time_travel_service")
app = FastAPI(title="HSAAI Time Travel", version="0.4.0")

class SnapshotRecord(BaseModel):
    timestamp: float
    label: str = ""
    entities: dict = {}
    metrics: dict = {}
    decisions_made: list = []
    active_risks: list = []
    financial_state: dict = {}

class ReplayRequest(BaseModel):
    timestamp: float
    original_decision: str
    alternative_decision: str
    original_outcome: dict = {}
    horizon_months: int = 6

@app.get("/health")
def health(): return {"status": "ok", "service": "time_travel", **time_travel_engine.stats()}

@app.post("/v1/snapshot")
def record_snapshot(snap: SnapshotRecord, claims: dict = Depends(_auth_dep)):
    state = HistoricalState(**snap.__dict__)
    time_travel_engine.record_snapshot(state)
    return {"recorded": True}

@app.post("/v1/replay")
async def replay(req: ReplayRequest, claims: dict = Depends(_auth_dep)):
    timeline = await time_travel_engine.replay_with_alternative(
        req.timestamp, req.original_decision, req.alternative_decision,
        req.original_outcome, req.horizon_months
    )
    return timeline.__dict__

@app.get("/v1/timelines")
def list_timelines(limit: int = 20, claims: dict = Depends(_auth_dep)):
    return {"timelines": time_travel_engine.list_timelines(limit)}

@app.get("/v1/stats")
def stats(claims: dict = Depends(_auth_dep)):
    return time_travel_engine.stats()
